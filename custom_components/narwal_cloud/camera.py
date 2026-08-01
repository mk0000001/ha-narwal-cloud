"""Live Dreame-compatible map cameras for Narwal Cloud."""

from __future__ import annotations

from datetime import datetime, timezone
import time
import zlib

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import NarwalCloudCoordinator
from .map_renderer import map_attributes, render_map, render_map_data


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[NarwalCloudCoordinator],
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [
            NarwalMapCamera(entry.runtime_data),
            NarwalMapCamera(entry.runtime_data, map_data_json=True),
        ]
    )


class NarwalMapCamera(CoordinatorEntity[NarwalCloudCoordinator], Camera):
    """Expose the latest map fetched from the cloud MQTT API."""

    _attr_has_entity_name = True
    _attr_name = "Map"
    _attr_content_type = "image/png"

    _attr_is_streaming = True

    def __init__(
        self,
        coordinator: NarwalCloudCoordinator,
        map_data_json: bool = False,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._map_data_json = map_data_json
        key = "map_data" if map_data_json else "map"
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        self._attr_name = None
        self._attr_translation_key = key
        if map_data_json:
            self._attr_entity_category = EntityCategory.CONFIG
            self._attr_entity_registry_enabled_default = False
        self._cached_key: tuple | None = None
        self._cached_image: bytes | None = None
        self._last_map_request = 0.0

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            manufacturer=NAME,
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        now = time.monotonic()
        if now - self._last_map_request >= 15:
            self._last_map_request = now
            self.coordinator.async_request_map_refresh()
        map_data = self.coordinator.map_data
        pose = map_data.robot_pose
        cache_key = (
            map_data.revision,
            map_data.width,
            map_data.height,
            map_data.border,
            zlib.crc32(map_data.compressed_grid),
            map_data.rooms,
            map_data.robot_pose_update_time,
            pose.x if pose else None,
            pose.y if pose else None,
            pose.angle if pose else None,
        )
        if cache_key != self._cached_key or self._cached_image is None:
            renderer = render_map_data if self._map_data_json else render_map
            self._cached_image = await self.hass.async_add_executor_job(
                renderer, map_data
            )
            self._cached_key = cache_key
        return self._cached_image or None

    @property
    def state(self) -> datetime | None:
        """Return the current map frame time like the Dreame camera."""
        timestamp = self.coordinator.map_data.robot_pose_update_time
        if timestamp:
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return self.coordinator.map_updated_at

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return map-card attributes on the rendered camera."""
        if self._map_data_json:
            return None
        return map_attributes(self.coordinator.map_data)
