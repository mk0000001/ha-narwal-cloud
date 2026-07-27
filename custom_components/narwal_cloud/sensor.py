"""Consumable lifetime sensors for Narwal Cloud."""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
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
    """Add one sensor for every timed consumable returned by Narwal."""
    coordinator = entry.runtime_data
    async_add_entities(
        NarwalConsumableSensor(coordinator, item)
        for item in coordinator.data.get("consumables", [])
    )


class NarwalConsumableSensor(
    CoordinatorEntity[NarwalCloudCoordinator], SensorEntity
):
    """Remaining replacement time for one consumable."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: NarwalCloudCoordinator,
        item: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._code = str(item.get("consumables_code") or item["type"])
        self._fallback_name = str(item["name"])
        self._attr_name = self._fallback_name
        self._attr_unique_id = (
            f"{coordinator.device_id}_consumable_{self._code}"
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            manufacturer=NAME,
        )

    def _item(self) -> dict[str, Any] | None:
        for item in self.coordinator.data.get("consumables", []):
            code = str(item.get("consumables_code") or item.get("type"))
            if code == self._code:
                return item
        return None

    @property
    def native_value(self) -> int | None:
        item = self._item()
        if item is None:
            return None
        total = int(item["total_duration"])
        used = max(0, int(item["usage_duration"]))
        return max(0, math.ceil((total - used) / 3600))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        item = self._item()
        if item is None:
            return {}
        total = int(item["total_duration"])
        used = max(0, int(item["usage_duration"]))
        remaining = max(0, total - used)
        return {
            "remaining_percent": round(remaining / total * 100, 1),
            "used_hours": round(used / 3600, 1),
            "total_hours": round(total / 3600, 1),
            "replacement_hint": item.get("subtitle"),
        }
