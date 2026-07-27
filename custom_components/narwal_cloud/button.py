"""Dock action buttons for Narwal Cloud."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Add the verified dock actions."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            NarwalDockButton(
                coordinator, "wash_and_dry_mop", "Wash and dry mops"
            ),
            NarwalDockButton(
                coordinator, "finish_station", "Finish mop washing/drying"
            ),
        ]
    )


class NarwalDockButton(CoordinatorEntity[NarwalCloudCoordinator], ButtonEntity):
    """Run one official-app dock command."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: NarwalCloudCoordinator, action: str, name: str
    ) -> None:
        super().__init__(coordinator)
        self._action = action
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.device_id}_{action}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            manufacturer=NAME,
        )

    async def async_press(self) -> None:
        await self.coordinator.client.async_send_task_command(
            self.coordinator.device_id,
            self.coordinator.product_id,
            self._action,
        )
        await self.coordinator.async_request_refresh()

