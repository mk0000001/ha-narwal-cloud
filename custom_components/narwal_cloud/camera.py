"""Static saved-map camera for Narwal Cloud."""

from __future__ import annotations

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import NarwalCloudCoordinator
from .map_renderer import render_map


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[NarwalCloudCoordinator],
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([NarwalMapCamera(entry.runtime_data)])


class NarwalMapCamera(CoordinatorEntity[NarwalCloudCoordinator], Camera):
    """Expose the latest map fetched from the cloud MQTT API."""

    _attr_has_entity_name = True
    _attr_name = "Map"
    _attr_content_type = "image/png"

    def __init__(self, coordinator: NarwalCloudCoordinator) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._attr_unique_id = f"{coordinator.device_id}_map"
        self._cached_key: tuple | None = None
        self._cached_image: bytes | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            manufacturer=NAME,
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        map_data = self.coordinator.map_data
        pose = map_data.robot_pose
        cache_key = (
            map_data.revision,
            map_data.robot_pose_update_time,
            pose.x if pose else None,
            pose.y if pose else None,
            pose.angle if pose else None,
        )
        if cache_key != self._cached_key or self._cached_image is None:
            self._cached_image = await self.hass.async_add_executor_job(
                render_map, map_data
            )
            self._cached_key = cache_key
        return self._cached_image or None
