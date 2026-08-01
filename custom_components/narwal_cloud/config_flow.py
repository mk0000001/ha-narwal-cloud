"""Config flow for Narwal Cloud."""

from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NarwalCloudAuthError, NarwalCloudClient, NarwalCloudError
from .const import (
    AUTH_METHOD_ACCOUNT,
    AUTH_METHOD_TOKEN,
    CONF_ACCESS_TOKEN,
    CONF_AUTH_METHOD,
    CONF_CLIENT_UUID,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PRODUCT_ID,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)


class NarwalCloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a Narwal account or app token pair."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Offer account login first and retain token compatibility."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["account", "token"],
        )

    async def async_step_account(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Sign in with the Narwal account and retain local credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = NarwalCloudClient(
                async_get_clientsession(self.hass),
                "",
                "",
                uuid.uuid4().hex,
                email=user_input[CONF_EMAIL],
                password=user_input[CONF_PASSWORD],
            )
            try:
                await client.async_login_with_email(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
                devices = await client.async_get_devices()
            except NarwalCloudAuthError:
                errors["base"] = "invalid_auth"
            except NarwalCloudError:
                errors["base"] = "cannot_connect"
            else:
                return await self._async_finish(
                    client,
                    devices,
                    {
                        CONF_AUTH_METHOD: AUTH_METHOD_ACCOUNT,
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="account",
            data_schema=_account_schema(user_input),
            errors=errors,
        )

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure using an existing app token pair."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = NarwalCloudClient(
                async_get_clientsession(self.hass),
                user_input[CONF_ACCESS_TOKEN],
                user_input[CONF_REFRESH_TOKEN],
                "",
            )
            try:
                devices = await client.async_get_devices()
            except NarwalCloudAuthError:
                errors["base"] = "invalid_auth"
            except NarwalCloudError:
                errors["base"] = "cannot_connect"
            else:
                return await self._async_finish(
                    client,
                    devices,
                    {CONF_AUTH_METHOD: AUTH_METHOD_TOKEN},
                )

        return self.async_show_form(
            step_id="token",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): _password_selector(),
                    vol.Required(CONF_REFRESH_TOKEN): _password_selector(),
                }
            ),
            errors=errors,
            description_placeholders={
                "token_guide_url": (
                    "https://github.com/mk0000001/ha-narwal-cloud/"
                    "blob/main/docs/token_setup.md"
                )
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Convert an existing token entry to account-managed login."""
        self._reauth_entry = self._get_reconfigure_entry()
        return await self._async_account_update(user_input, "reconfigure")

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Request account credentials after all automatic recovery failed."""
        self._reauth_entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm replacement Narwal credentials."""
        return await self._async_account_update(user_input, "reauth_confirm")

    async def _async_account_update(
        self,
        user_input: dict[str, Any] | None,
        step_id: str,
    ) -> config_entries.ConfigFlowResult:
        entry = self._reauth_entry
        errors: dict[str, str] = {}
        if user_input is not None:
            client = NarwalCloudClient(
                async_get_clientsession(self.hass),
                "",
                "",
                entry.data.get(CONF_CLIENT_UUID, uuid.uuid4().hex),
                email=user_input[CONF_EMAIL],
                password=user_input[CONF_PASSWORD],
            )
            try:
                await client.async_login_with_email(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
                devices = await client.async_get_devices()
                device = _matching_device(devices, entry.data[CONF_DEVICE_ID])
            except NarwalCloudAuthError:
                errors["base"] = "invalid_auth"
            except NarwalCloudError:
                errors["base"] = "cannot_connect"
            else:
                if device is None:
                    errors["base"] = "device_not_found"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates={
                            **entry.data,
                            CONF_AUTH_METHOD: AUTH_METHOD_ACCOUNT,
                            CONF_EMAIL: user_input[CONF_EMAIL],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_ACCESS_TOKEN: client.access_token,
                            CONF_REFRESH_TOKEN: client.refresh_token,
                            CONF_CLIENT_UUID: client.client_uuid,
                        },
                    )

        return self.async_show_form(
            step_id=step_id,
            data_schema=_account_schema(
                user_input,
                entry.data.get(CONF_EMAIL) if entry is not None else None,
            ),
            errors=errors,
        )

    async def _async_finish(
        self,
        client: NarwalCloudClient,
        devices: list[dict[str, Any]],
        auth_data: dict[str, Any],
    ) -> config_entries.ConfigFlowResult:
        if not devices:
            return self.async_abort(reason="no_devices")
        device = devices[0]
        device_id = device.get("deviceId")
        product_id = device.get("productId")
        if not isinstance(device_id, str) or not isinstance(product_id, str):
            return self.async_abort(reason="invalid_response")

        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=str(device.get("robotName") or "Narwal"),
            data={
                **auth_data,
                CONF_ACCESS_TOKEN: client.access_token,
                CONF_REFRESH_TOKEN: client.refresh_token,
                CONF_CLIENT_UUID: client.client_uuid,
                CONF_DEVICE_ID: device_id,
                CONF_PRODUCT_ID: product_id,
                CONF_DEVICE_NAME: str(device.get("robotName") or "Narwal"),
            },
        )


def _account_schema(
    user_input: dict[str, Any] | None,
    saved_email: str | None = None,
) -> vol.Schema:
    values = user_input or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_EMAIL,
                default=values.get(CONF_EMAIL, saved_email or ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
            ),
            vol.Required(CONF_PASSWORD): _password_selector(),
        }
    )


def _password_selector() -> selector.TextSelector:
    return selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    )


def _matching_device(
    devices: list[dict[str, Any]], device_id: str
) -> dict[str, Any] | None:
    return next(
        (device for device in devices if device.get("deviceId") == device_id),
        None,
    )
