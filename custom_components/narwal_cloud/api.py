"""Small async client for Narwal's Korean cloud endpoint.

Only data required by Home Assistant is retained. Tokens never appear in
logging or exceptions.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import API_BASE_URL, CLIENT_APPLICATION_ID, CLIENT_APP_VERSION, CLIENT_VERSION_CODE
from .auth import (
    NarwalCredentials,
    encrypt_account_password,
    token_pair_from_payload,
)
from .mqtt import (
    NarwalMqttError,
    async_publish_task_command,
    async_request,
    async_request_base_status,
)
from .protocol import (
    NarwalCleanPlan,
    NarwalMap,
    parse_clean_plans_response,
    parse_base_status_response,
    parse_map_response,
)

TokenUpdateCallback = Callable[[str, str], Awaitable[None]]


class NarwalCloudError(Exception):
    """Base class for cloud errors."""


class NarwalCloudAuthError(NarwalCloudError):
    """Authentication expired or was rejected."""


class NarwalCloudClient:
    """Narwal cloud API client based on the official Android app contract."""

    def __init__(
        self,
        session: ClientSession,
        access_token: str,
        refresh_token: str,
        client_uuid: str,
        on_token_update: TokenUpdateCallback | None = None,
        email: str | None = None,
        password: str | None = None,
    ) -> None:
        self._session = session
        self._credentials = NarwalCredentials(
            access_token, refresh_token, client_uuid
        )
        self._on_token_update = on_token_update
        self._email = email
        self._password = password

    @property
    def access_token(self) -> str:
        """Return the latest rotated access token without logging it."""
        return self._credentials.access_token

    @property
    def refresh_token(self) -> str:
        """Return the latest rotated refresh token without logging it."""
        return self._credentials.refresh_token

    @property
    def client_uuid(self) -> str:
        """Return the account UUID required by Narwal MQTT."""
        return self._credentials.client_uuid

    def _headers(self) -> dict[str, str]:
        """Return the non-identifying Android client headers expected by Narwal."""
        return {
            "accept-encoding": "gzip",
            "aiot-application-id": CLIENT_APPLICATION_ID,
            "app-language": "en-US",
            "app-version": CLIENT_APP_VERSION,
            "app_type": "normal",
            "app_version": CLIENT_APP_VERSION,
            "auth-token": self.access_token,
            "authorization": self.access_token,
            "country_code": "KR",
            "did": self.client_uuid,
            "is_app": "true",
            "is_beta": "false",
            "ismainland": "0",
            "language_code": "en-US",
            "platform": "android",
            "uuid": self.client_uuid,
            "version_code": CLIENT_VERSION_CODE,
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        """Perform a request and refresh once if the access token is rejected."""
        try:
            async with self._session.request(
                method,
                f"{API_BASE_URL}{path}",
                headers=self._headers(),
                params=params,
                json=json,
                timeout=20,
            ) as response:
                if response.status in (401, 403):
                    if retry_auth:
                        await self.async_refresh_token()
                        return await self._request(
                            method, path, params=params, json=json, retry_auth=False
                        )
                    raise NarwalCloudAuthError("Narwal rejected the access token")
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except NarwalCloudAuthError:
            raise
        except (ClientError, TimeoutError, ValueError) as err:
            raise NarwalCloudError("Unable to reach Narwal Cloud") from err

        if not isinstance(payload, dict):
            raise NarwalCloudError("Narwal returned an invalid response")
        code = payload.get("code")
        message = payload.get("msg") or payload.get("message")
        if code == -1 and isinstance(message, str) and "token" in message.lower():
            if retry_auth:
                await self.async_refresh_token()
                return await self._request(
                    method, path, params=params, json=json, retry_auth=False
                )
            raise NarwalCloudAuthError("Narwal rejected the access token")
        if payload.get("success") is False:
            raise NarwalCloudError("Narwal API request failed")
        return payload

    async def async_refresh_token(self) -> None:
        """Exchange the stored refresh token and persist the rotated pair."""
        try:
            async with self._session.post(
                f"{API_BASE_URL}/user-authentication-server/v1/token/refresh",
                headers={**self._headers(), "content-type": "application/json; charset=utf-8"},
                json={"refreshToken": self.refresh_token},
                timeout=20,
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            if self._email is not None and self._password is not None:
                await self.async_login_with_email(self._email, self._password)
                return
            raise NarwalCloudAuthError(
                "Narwal session needs to be connected again"
            ) from err

        pair = token_pair_from_payload(payload) if isinstance(payload, dict) else None
        if pair is None:
            if self._email is not None and self._password is not None:
                await self.async_login_with_email(self._email, self._password)
                return
            raise NarwalCloudAuthError(
                "Narwal session needs to be connected again"
            )

        await self._async_store_token_pair(*pair)

    async def async_login_with_email(self, email: str, password: str) -> None:
        """Create a Narwal app session from an email and password."""
        encrypted_password = encrypt_account_password(password)
        headers = self._headers()
        headers.pop("auth-token", None)
        headers.pop("authorization", None)
        try:
            async with self._session.post(
                f"{API_BASE_URL}/user-authentication-server/v2/login/loginByEmail",
                headers={
                    **headers,
                    "content-type": "application/json; charset=utf-8",
                },
                # The current app names the RSA ciphertext encrypted_password.
                # password is included for compatibility with older regional
                # gateways that used the earlier field name.
                json={
                    "email": email,
                    "encrypted_password": encrypted_password,
                    "password": encrypted_password,
                },
                timeout=20,
            ) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise NarwalCloudAuthError("Unable to sign in to Narwal") from err

        pair = token_pair_from_payload(payload) if isinstance(payload, dict) else None
        if pair is None:
            raise NarwalCloudAuthError("Narwal rejected the account login")

        self._email = email
        self._password = password
        await self._async_store_token_pair(*pair)

    async def _async_store_token_pair(
        self, access_token: str, refresh_token: str
    ) -> None:
        """Rotate and persist a newly issued Narwal token pair."""
        self._credentials.rotate(access_token, refresh_token)
        if self._on_token_update is not None:
            await self._on_token_update(access_token, refresh_token)

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Return the account's bound Narwal devices."""
        payload = await self._request(
            "GET", "/user-device-platform-server/device-info/getDeviceInfoList"
        )
        result = payload.get("result")
        devices = result.get("deviceInfoList") if isinstance(result, dict) else None
        if not isinstance(devices, list):
            raise NarwalCloudError("No Narwal devices were returned")
        return [device for device in devices if isinstance(device, dict)]

    async def async_get_device_info(
        self, device_id: str, product_id: str
    ) -> dict[str, Any]:
        """Return model and firmware data for one robot."""
        payload = await self._request(
            "GET",
            "/sweeper-app-server/v1/sweeper/getDeviceInfo/",
            params={"device_id": device_id, "product_id": product_id},
        )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise NarwalCloudError("Narwal did not return device information")
        return result

    async def async_get_work_status(
        self, device_id: str, product_id: str
    ) -> dict[str, Any]:
        """Return the cloud work-state used by the official app home screen."""
        payload = await self._request(
            "GET",
            "/device-task/work-status/get",
            params={"device_id": device_id, "product_id": product_id, "source": "0"},
        )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise NarwalCloudError("Narwal did not return the robot state")
        return result

    async def async_get_base_status(
        self, device_id: str, product_id: str
    ) -> dict[str, int]:
        """Return live battery data from the robot MQTT broadcast."""
        broker_url = await self.async_get_broker_url()
        try:
            async with asyncio.timeout(20):
                payload = await async_request_base_status(
                    broker_url,
                    self.access_token,
                    self.client_uuid,
                    product_id,
                    device_id,
                )
            return parse_base_status_response(payload)
        except (NarwalMqttError, TimeoutError, ValueError) as err:
            raise NarwalCloudError(
                "Unable to read the Narwal base status"
            ) from err

    async def async_get_broker_url(self) -> str:
        """Return the regional MQTT broker selected by Narwal."""
        payload = await self._request(
            "GET",
            "/iot-broker-discover/app/v1/broker/discover",
            params={"country": "KR"},
        )
        result = payload.get("result")
        if not isinstance(result, str) or "://" not in result:
            raise NarwalCloudError("Narwal did not return an MQTT broker")
        return result

    async def async_get_consumables(
        self, device_id: str, product_id: str
    ) -> list[dict[str, Any]]:
        """Return consumable counters from the endpoint used by the app."""
        payload = await self._request(
            "POST",
            "/consumables-management-app-server/v3/consumables/list",
            json={"deviceId": device_id, "productId": product_id},
        )
        result = payload.get("result")
        if not isinstance(result, list):
            raise NarwalCloudError("Narwal did not return consumable data")
        return [
            item
            for item in result
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and isinstance(item.get("total_duration"), int)
            and item["total_duration"] > 0
            and isinstance(item.get("usage_duration"), int)
            and item.get("progress_bar_switch") == 1
        ]

    async def async_send_task_command(
        self,
        device_id: str,
        product_id: str,
        action: str,
        room_ids: list[int] | None = None,
        *,
        mode: int = 1,
        suction: int = 2,
        humidity: int = 2,
        cycles: int = 1,
        room_templates: dict[int, bytes] | None = None,
    ) -> None:
        """Send a captured task command through Narwal MQTT."""
        broker_url = await self.async_get_broker_url()
        try:
            await async_publish_task_command(
                broker_url,
                self.access_token,
                self.client_uuid,
                product_id,
                device_id,
                action,
                room_ids,
                mode=mode,
                suction=suction,
                humidity=humidity,
                cycles=cycles,
                room_templates=room_templates,
            )
        except NarwalMqttError as err:
            raise NarwalCloudError(str(err)) from err

    async def async_get_map(
        self, device_id: str, product_id: str
    ) -> NarwalMap:
        """Return the robot's current saved map and room metadata."""
        broker_url = await self.async_get_broker_url()
        try:
            # An already-online robot answers the focused request reliably and
            # avoids activation broadcasts racing the map response.
            async with asyncio.timeout(20):
                payload = await async_request(
                    broker_url,
                    self.access_token,
                    self.client_uuid,
                    product_id,
                    device_id,
                    "map/get_map",
                    b"\x08\x00\x10\x00",
                )
        except (NarwalMqttError, TimeoutError, ValueError) as err:
            try:
                # Sleeping older Freo firmware needs the official app-style
                # activation burst before it will answer the same request.
                async with asyncio.timeout(60):
                    payload = await async_request(
                        broker_url,
                        self.access_token,
                        self.client_uuid,
                        product_id,
                        device_id,
                        "map/get_map",
                        b"\x08\x00\x10\x00",
                        activate_robot=True,
                    )
            except (NarwalMqttError, TimeoutError, ValueError) as retry_err:
                raise NarwalCloudError(
                    "Unable to read the Narwal map"
                ) from retry_err
        return parse_map_response(payload)

    async def async_get_clean_plans(
        self, device_id: str, product_id: str
    ) -> tuple[NarwalCleanPlan, ...]:
        """Return the five cleaning plans configured by the official app."""
        broker_url = await self.async_get_broker_url()
        try:
            async with asyncio.timeout(60):
                payload = await async_request(
                    broker_url,
                    self.access_token,
                    self.client_uuid,
                    product_id,
                    device_id,
                    "clean/plan/get",
                    activate_robot=True,
                )
            return parse_clean_plans_response(payload)
        except (NarwalMqttError, TimeoutError, ValueError) as err:
            raise NarwalCloudError("Unable to read Narwal cleaning plans") from err
