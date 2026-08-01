"""Robot mode binary sensors for Narwal Cloud."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import NarwalCloudCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[NarwalCloudCoordinator],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add mode indicators shown directly on the device page."""
    async_add_entities([NarwalTurboModeSensor(entry.runtime_data)])


class NarwalTurboModeSensor(
    CoordinatorEntity[NarwalCloudCoordinator], BinarySensorEntity
):
    """Show whether the selected suction setting is turbo/strong."""

    _attr_has_entity_name = True
    _attr_translation_key = "turbo_mode"

    def __init__(self, coordinator: NarwalCloudCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_turbo_mode"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            manufacturer=NAME,
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.suction_power >= 3
