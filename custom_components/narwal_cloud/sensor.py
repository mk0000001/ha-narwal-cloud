"""Consumable lifetime sensors for Narwal Cloud."""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
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
    """Add robot state and consumable sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        NarwalBatterySensor(coordinator),
        NarwalStatusSensor(coordinator, "movement_status"),
        NarwalStatusSensor(coordinator, "cleaning_status"),
    ]
    entities.extend(
        NarwalConsumableSensor(coordinator, item)
        for item in coordinator.data.get("consumables", [])
    )
    async_add_entities(entities)


def battery_percentage(status: dict[str, Any]) -> int | None:
    """Read the battery value across known Narwal API variants."""
    for key in (
        "battery_percentage",
        "battery_level",
        "battery",
        "electric_quantity",
    ):
        value = status.get(key)
        if isinstance(value, bool) or value is None:
            continue
        try:
            percentage = round(float(value))
        except (TypeError, ValueError):
            continue
        if 0 <= percentage <= 100:
            return percentage
    return None


def movement_status(status: dict[str, Any]) -> str:
    """Return a stable HA enum for the robot's current movement state."""
    if status.get("fault"):
        return "error"
    if status.get("recall"):
        return "returning"
    if status.get("pause"):
        return "paused"
    if status.get("station_work"):
        return "station_work"
    if status.get("in_station"):
        charging = any(
            bool(status.get(key))
            for key in ("charging", "charge", "is_charging")
        )
        battery = battery_percentage(status)
        return "charging" if charging or battery is not None and battery < 100 else "docked"
    if status.get("free"):
        return "idle"
    return "cleaning"


class NarwalBatterySensor(
    CoordinatorEntity[NarwalCloudCoordinator], SensorEntity
):
    """Expose battery as a first-class device-page sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: NarwalCloudCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device_id}_battery"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            manufacturer=NAME,
        )

    @property
    def native_value(self) -> int | None:
        return battery_percentage(self.coordinator.data["status"])


class NarwalStatusSensor(
    CoordinatorEntity[NarwalCloudCoordinator], SensorEntity
):
    """Expose Samsung-style movement and cleaning state entries."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(
        self, coordinator: NarwalCloudCoordinator, key: str
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.device_id}_{key}"
        self._attr_options = (
            [
                "charging",
                "cleaning",
                "docked",
                "error",
                "idle",
                "paused",
                "returning",
                "station_work",
            ]
            if key == "movement_status"
            else [
                "cleaning",
                "error",
                "paused",
                "returning",
                "station_work",
                "stopped",
            ]
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            manufacturer=NAME,
        )

    @property
    def native_value(self) -> str:
        status = self.coordinator.data["status"]
        current = movement_status(status)
        if self._key == "movement_status":
            return current
        if current in ("charging", "docked", "idle"):
            return "stopped"
        return current


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
