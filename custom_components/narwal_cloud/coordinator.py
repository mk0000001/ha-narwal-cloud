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

MAP_REFRESH_INTERVAL = timedelta(minutes=1)
_LOGGER = logging.getLogger(__name__)


class NarwalCloudCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the exact state endpoint used by the official Narwal app."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: NarwalCloudClient,
        device_id: str,
        product_id: str,
    ) -> None:
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self.device_id = device_id
        self.product_id = product_id
        self.map_data = NarwalMap()
        self.clean_plans: tuple[NarwalCleanPlan, ...] = ()
        self._map_updated_at: datetime | None = None
        self._map_refresh_task: asyncio.Task[None] | None = None
        self.cleaning_mode = 1
        self.suction_power = 2
        self.mop_humidity = 2
        self.cleaning_cycles = 1

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            device, status, consumables = await asyncio.gather(
                self.client.async_get_device_info(self.device_id, self.product_id),
                self.client.async_get_work_status(self.device_id, self.product_id),
                self.client.async_get_consumables(self.device_id, self.product_id),
            )
            now = datetime.now()
            if (
                self._map_updated_at is None
                or now - self._map_updated_at >= MAP_REFRESH_INTERVAL
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

    async def _async_refresh_map_metadata(self) -> None:
        """Refresh live map data without blocking core device polling."""
        try:
            self.map_data = await self.client.async_get_map(
                self.device_id, self.product_id
            )
            self.clean_plans = await self.client.async_get_clean_plans(
                self.device_id, self.product_id
            )
            self._map_updated_at = datetime.now()
        except NarwalCloudError:
            # Status polling remains useful when the robot or broker
            # temporarily declines optional map metadata.
            _LOGGER.warning(
                "Unable to refresh Narwal map metadata",
                exc_info=True,
            )
