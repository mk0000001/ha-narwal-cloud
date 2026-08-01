"""Cleaning option selectors for Narwal Cloud."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import NarwalCloudCoordinator

MODE_OPTIONS = {
    "Freo Mind": 1,
    "Vacuum": 2,
    "Mop": 3,
    "Vacuum and mop": 4,
    "Vacuum then mop": 5,
}
SUCTION_OPTIONS = {"Quiet": 1, "Standard": 2, "Strong": 3}
HUMIDITY_OPTIONS = {"Slightly dry": 1, "Standard": 2, "Slightly wet": 3}
CYCLE_OPTIONS = {"1 time": 1, "2 times": 2, "3 times": 3}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[NarwalCloudCoordinator],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add cleaning option selectors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            NarwalOptionSelect(
                coordinator, "cleaning_mode", "Cleaning mode", MODE_OPTIONS
            ),
            NarwalOptionSelect(
                coordinator, "suction_power", "Suction power", SUCTION_OPTIONS
            ),
            NarwalOptionSelect(
                coordinator, "mop_humidity", "Mop humidity", HUMIDITY_OPTIONS
            ),
            NarwalOptionSelect(
                coordinator, "cleaning_cycles", "Cleaning cycles", CYCLE_OPTIONS
            ),
        ]
    )


class NarwalOptionSelect(CoordinatorEntity[NarwalCloudCoordinator], SelectEntity):
    """A locally stored option used when the next task starts."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NarwalCloudCoordinator,
        key: str,
        name: str,
        options: dict[str, int],
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._mapping = options
        self._attr_name = name
        self._attr_options = list(options)
        self._attr_unique_id = f"{coordinator.device_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            manufacturer=NAME,
        )

    @property
    def current_option(self) -> str | None:
        value = getattr(self.coordinator, self._key)
        return next(
            (name for name, option_value in self._mapping.items()
             if option_value == value),
            None,
        )

    async def async_select_option(self, option: str) -> None:
        setattr(self.coordinator, self._key, self._mapping[option])
        self.async_write_ha_state()
        self.coordinator.async_update_listeners()

