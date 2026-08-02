"""Data coordinator for Narwal Cloud."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NarwalCloudAuthError, NarwalCloudClient, NarwalCloudError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .protocol import NarwalCleanPlan, NarwalMap

MAP_REFRESH_INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)


class NarwalCloudCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the exact state endpoint used by the official Narwal app."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: NarwalCloudClient,
        device_id: str,
        product_id: str,
        scan_interval: timedelta = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=scan_interval,
        )
        self.client = client
        self.device_id = device_id
        self.product_id = product_id
        self.map_data = NarwalMap()
        self.clean_plans: tuple[NarwalCleanPlan, ...] = ()
        self._map_updated_at: datetime | None = None
        self._map_attempted_at: datetime | None = None
        self._map_refresh_task: asyncio.Task[None] | None = None
        self.cleaning_mode = 1
        self.suction_power = 2
        self.mop_humidity = 2
        self.cleaning_cycles = 1

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            device, status = await asyncio.gather(
                self.client.async_get_device_info(self.device_id, self.product_id),
                self.client.async_get_work_status(self.device_id, self.product_id),
            )
            # Narwal intermittently returns malformed consumable data when
            # broker discovery and consumable REST calls overlap. Keep these
            # optional reads sequential so one feature cannot block setup.
            base_status = await self._async_get_base_status()
            consumables = await self._async_get_consumables()
            status = {**status, **base_status}
            now = datetime.now().astimezone()
            last_map_activity = self._map_updated_at or self._map_attempted_at
            if (
                last_map_activity is None
                or now - last_map_activity >= MAP_REFRESH_INTERVAL
            ):
                if (
                    self._map_refresh_task is None
                    or self._map_refresh_task.done()
                ):
                    # Map data is optional and its sleeping-robot handshake can
                    # take several seconds. Never hold up HA startup or the
                    # primary vacuum state while it refreshes.
                    self._map_refresh_task = asyncio.create_task(
                        self._async_refresh_map_metadata(),
                        name=f"{DOMAIN}-map-refresh",
                    )
        except NarwalCloudAuthError as err:
            raise ConfigEntryAuthFailed from err
        except NarwalCloudError as err:
            raise UpdateFailed(str(err)) from err
        return {
            "device": device,
            "status": status,
            "map": self.map_data,
            "clean_plans": self.clean_plans,
            "consumables": consumables,
        }

    async def _async_get_base_status(self) -> dict[str, int]:
        """Read optional live battery data without failing core polling."""
        try:
            return await self.client.async_get_base_status(
                self.device_id, self.product_id
            )
        except NarwalCloudError:
            _LOGGER.warning(
                "Unable to refresh Narwal battery status",
                exc_info=True,
            )
            return {}

    async def _async_get_consumables(self) -> list[dict[str, Any]]:
        """Read optional consumables without failing integration setup."""
        try:
            return await self.client.async_get_consumables(
                self.device_id, self.product_id
            )
        except NarwalCloudError:
            _LOGGER.warning(
                "Unable to refresh Narwal consumable data",
                exc_info=True,
            )
            if self.data is not None:
                return list(self.data.get("consumables", []))
            return []

    async def _async_refresh_map_metadata(
        self, refresh_plans: bool = True
    ) -> None:
        """Refresh live map data without blocking core device polling."""
        self._map_attempted_at = datetime.now().astimezone()
        try:
            # These requests use the same MQTT client id, so they must remain
            # sequential or the broker disconnects the first session.
            map_data = await self.client.async_get_map(
                self.device_id, self.product_id
            )
            clean_plans = self.clean_plans
            if refresh_plans or not clean_plans:
                clean_plans = await self.client.async_get_clean_plans(
                    self.device_id, self.product_id
                )
            self.map_data = map_data
            self.clean_plans = clean_plans
            self._map_updated_at = datetime.now().astimezone()
            if self.data is not None:
                self.async_set_updated_data(
                    {
                        **self.data,
                        "map": self.map_data,
                        "clean_plans": self.clean_plans,
                    }
                )
        except NarwalCloudError:
            # Status polling remains useful when the robot or broker
            # temporarily declines optional map metadata.
            _LOGGER.debug("Narwal map is temporarily unavailable", exc_info=True)

    @property
    def map_updated_at(self) -> datetime | None:
        """Return the time the latest cloud map completed loading."""
        return self._map_updated_at

    def async_request_map_refresh(self) -> None:
        """Schedule a map refresh without blocking a camera request."""
        if self._map_refresh_task is None or self._map_refresh_task.done():
            self._map_refresh_task = self.hass.async_create_task(
                self._async_refresh_map_metadata(refresh_plans=False),
                name=f"{DOMAIN}-map-camera-refresh",
            )

    async def async_refresh_rooms(self) -> None:
        """Refresh map rooms and official per-room cleaning templates."""
        if self._map_refresh_task is not None and not self._map_refresh_task.done():
            await self._map_refresh_task
            return
        await self._async_refresh_map_metadata(refresh_plans=True)

    def room_templates_for_mode(self, mode: int) -> dict[int, bytes]:
        """Return exact official room templates for a cleaning mode."""
        plan = next((plan for plan in self.clean_plans if plan.mode == mode), None)
        return dict(plan.room_templates) if plan is not None else {}
