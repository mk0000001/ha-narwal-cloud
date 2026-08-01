"""Vacuum entity for the Narwal cloud coordinator."""

from __future__ import annotations

from typing import Any

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)

try:
    from homeassistant.components.vacuum import Segment
except ImportError:
    Segment = None
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_NAME, DOMAIN, NAME
from .coordinator import NarwalCloudCoordinator
from .select import (
    CYCLE_OPTIONS,
    HUMIDITY_OPTIONS,
    MODE_OPTIONS,
    SUCTION_OPTIONS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[NarwalCloudCoordinator],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the configured Narwal robot."""
    async_add_entities([NarwalCloudVacuum(entry.runtime_data, entry)])


class NarwalCloudVacuum(CoordinatorEntity[NarwalCloudCoordinator], StateVacuumEntity):
    """Narwal entity backed by cloud state and captured MQTT commands."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        VacuumEntityFeature.STATE
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
    ) | (
        VacuumEntityFeature.CLEAN_AREA
        if Segment is not None
        else VacuumEntityFeature(0)
    )

    def __init__(self, coordinator: NarwalCloudCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = coordinator.device_id

    @property
    def device_info(self) -> DeviceInfo:
        """Expose robot model details discovered from Narwal Cloud."""
        device = self.coordinator.data["device"]
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device_id)},
            manufacturer=NAME,
            name=str(device.get("robot_name") or self._entry.data[CONF_DEVICE_NAME]),
            model=str(device.get("robot_model") or device.get("product_name") or "Robot vacuum"),
            sw_version=str(device.get("firmware_version") or "") or None,
        )

    @property
    def available(self) -> bool:
        """Cloud reachability and robot connectivity are reported separately."""
        return super().available and bool(self.coordinator.data["status"].get("online"))

    @property
    def activity(self) -> VacuumActivity | None:
        """Map Narwal's work-status booleans to HA activity."""
        status = self.coordinator.data["status"]
        if status.get("fault"):
            return VacuumActivity.ERROR
        if status.get("recall"):
            return VacuumActivity.RETURNING
        if status.get("pause"):
            return VacuumActivity.PAUSED
        if status.get("in_station"):
            return VacuumActivity.DOCKED
        if status.get("free"):
            return VacuumActivity.IDLE
        return VacuumActivity.CLEANING

    @property
    def fan_speed_list(self) -> list[str]:
        """Expose suction settings inside the standard vacuum entity."""
        return list(SUCTION_OPTIONS)

    @property
    def fan_speed(self) -> str | None:
        return next(
            (
                name
                for name, value in SUCTION_OPTIONS.items()
                if value == self.coordinator.suction_power
            ),
            None,
        )

    async def async_set_fan_speed(
        self, fan_speed: str, **kwargs: Any
    ) -> None:
        """Set suction power for the next cleaning task."""
        self.coordinator.suction_power = SUCTION_OPTIONS[fan_speed]
        self.async_write_ha_state()
        self.coordinator.async_update_listeners()

    async def async_pause(self) -> None:
        """Pause the current Narwal task."""
        await self.coordinator.client.async_send_task_command(
            self.coordinator.device_id,
            self.coordinator.product_id,
            "pause",
        )
        await self.coordinator.async_request_refresh()

    async def async_start(self) -> None:
        """Resume a paused task or create a new whole-house Freo Mind task."""
        status = self.coordinator.data["status"]
        if (
            status.get("pause")
            and not status.get("free")
            and not status.get("in_station")
        ):
            action = "resume"
            room_ids = None
        else:
            action = "easy_clean_start"
            room_ids = [
                room.room_id for room in self.coordinator.map_data.rooms
            ]
        await self.coordinator.client.async_send_task_command(
            self.coordinator.device_id,
            self.coordinator.product_id,
            action,
            room_ids,
            mode=self.coordinator.cleaning_mode,
            suction=self.coordinator.suction_power,
            humidity=self.coordinator.mop_humidity,
            cycles=self.coordinator.cleaning_cycles,
            room_templates=self.coordinator.room_templates_for_mode(
                self.coordinator.cleaning_mode
            ),
        )
        await self.coordinator.async_request_refresh()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Recall the robot to its dock."""
        await self.coordinator.client.async_send_task_command(
            self.coordinator.device_id,
            self.coordinator.product_id,
            "recall",
        )
        await self.coordinator.async_request_refresh()

    async def async_get_segments(self) -> list:
        """Expose saved-map rooms to Home Assistant's room picker."""
        if Segment is None:
            return []
        if not self.coordinator.map_data.rooms:
            await self.coordinator.async_refresh_rooms()
        return [
            Segment(id=str(room.room_id), name=room.name, group="Rooms")
            for room in self.coordinator.map_data.rooms
        ]

    async def async_clean_segments(
        self, segment_ids: list[str], **kwargs: Any
    ) -> None:
        """Start cleaning only the selected map rooms."""
        if not self.coordinator.map_data.rooms:
            await self.coordinator.async_refresh_rooms()
        available_ids = {room.room_id for room in self.coordinator.map_data.rooms}
        room_ids: list[int] = []
        for segment_id in segment_ids:
            try:
                room_id = int(segment_id)
            except (TypeError, ValueError):
                continue
            if room_id in available_ids and room_id not in room_ids:
                room_ids.append(room_id)
        if not room_ids:
            raise ValueError("No valid Narwal rooms were selected")
        await self.coordinator.client.async_send_task_command(
            self.coordinator.device_id,
            self.coordinator.product_id,
            "easy_clean_start",
            room_ids,
            mode=self.coordinator.cleaning_mode,
            suction=self.coordinator.suction_power,
            humidity=self.coordinator.mop_humidity,
            cycles=self.coordinator.cleaning_cycles,
            room_templates=self.coordinator.room_templates_for_mode(
                self.coordinator.cleaning_mode
            ),
        )
        await self.coordinator.async_request_refresh()

    async def async_stop(self, **kwargs: Any) -> None:
        """End the active Narwal task."""
        await self.coordinator.client.async_send_task_command(
            self.coordinator.device_id,
            self.coordinator.product_id,
            "force_end",
        )
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Publish non-sensitive work state for automations and diagnostics."""
        status = self.coordinator.data["status"]
        pose = self.coordinator.map_data.robot_pose
        return {
            "in_station": status.get("in_station"),
            "paused": status.get("pause"),
            "returning": status.get("recall"),
            "station_work": status.get("station_work"),
            "fault": status.get("fault"),
            "fault_code": status.get("fault_code"),
            "cleaning_mode": _option_name(
                MODE_OPTIONS, self.coordinator.cleaning_mode
            ),
            "suction_power": _option_name(
                SUCTION_OPTIONS, self.coordinator.suction_power
            ),
            "mop_humidity": _option_name(
                HUMIDITY_OPTIONS, self.coordinator.mop_humidity
            ),
            "cleaning_cycles": _option_name(
                CYCLE_OPTIONS, self.coordinator.cleaning_cycles
            ),
            "rooms": {
                str(room.room_id): room.name
                for room in self.coordinator.map_data.rooms
            },
            "robot_position": (
                {
                    "x": round(pose.x, 3),
                    "y": round(pose.y, 3),
                    "angle": round(pose.angle, 3),
                    "updated_at": (
                        self.coordinator.map_data.robot_pose_update_time or None
                    ),
                }
                if pose is not None
                else None
            ),
        }


def _option_name(options: dict[str, int], value: int) -> str | None:
    return next(
        (name for name, option_value in options.items() if option_value == value),
        None,
    )
