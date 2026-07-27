"""Small protobuf helpers for the Narwal cloud MQTT protocol.

Narwal does not publish protobuf schemas for these messages.  This module
therefore decodes only the fields that have been verified against YJCC012
traffic captured from the official app.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import struct


@dataclass(frozen=True)
class ProtoField:
    """One protobuf field preserving its wire type and raw value."""

    number: int
    wire_type: int
    value: int | bytes


@dataclass(frozen=True)
class NarwalRoom:
    """A selectable room from the current saved map."""

    room_id: int
    name: str
    room_type: int = 0
    instance_index: int = 0


@dataclass(frozen=True)
class NarwalPose:
    """One robot-map pose in Narwal's coordinate system."""

    x: float = 0.0
    y: float = 0.0
    angle: float = 0.0


@dataclass(frozen=True)
class NarwalMap:
    """Map, rooms, and live poses returned by `/map/get_map`."""

    revision: int = 0
    resolution: int = 0
    width: int = 0
    height: int = 0
    rooms: tuple[NarwalRoom, ...] = ()
    compressed_grid: bytes = b""
    border: tuple[int, int, int, int] = (0, 0, 0, 0)
    origin: NarwalPose | None = None
    station: NarwalPose | None = None
    robot_pose: NarwalPose | None = None
    robot_pose_update_time: int = 0


@dataclass(frozen=True)
class NarwalCleanPlan:
    """One official-app cleaning plan template."""

    plan_id: int
    mode: int
    room_templates: dict[int, bytes] = field(default_factory=dict)


ROOM_TYPE_NAMES = {
    0: "Room",
    1: "Main bedroom",
    2: "Bedroom",
    3: "Living room",
    4: "Kitchen",
    5: "Study",
    6: "Bathroom",
    7: "Dining room",
    8: "Corridor",
    9: "Balcony",
    # YJCC012 reports its corridor with room type 10.
    10: "Corridor",
    11: "Cloakroom",
    12: "Nursery",
    13: "Recreation room",
    14: "Shower room",
    15: "Other room",
}


def read_varint(data: bytes, position: int = 0) -> tuple[int, int]:
    """Read one protobuf/MQTT variable-length integer."""
    value = 0
    shift = 0
    while position < len(data) and shift < 70:
        byte = data[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, position
        shift += 7
    raise ValueError("Invalid or truncated varint")


def decode_fields(data: bytes) -> list[ProtoField]:
    """Decode protobuf primitives without guessing nested message types."""
    fields: list[ProtoField] = []
    position = 0
    while position < len(data):
        key, position = read_varint(data, position)
        number = key >> 3
        wire_type = key & 7
        if number == 0:
            raise ValueError("Invalid protobuf field number")
        if wire_type == 0:
            value, position = read_varint(data, position)
        elif wire_type == 1:
            end = position + 8
            if end > len(data):
                raise ValueError("Truncated fixed64 field")
            value = data[position:end]
            position = end
        elif wire_type == 2:
            size, position = read_varint(data, position)
            end = position + size
            if end > len(data):
                raise ValueError("Truncated length-delimited field")
            value = data[position:end]
            position = end
        elif wire_type == 5:
            end = position + 4
            if end > len(data):
                raise ValueError("Truncated fixed32 field")
            value = data[position:end]
            position = end
        else:
            raise ValueError(f"Unsupported protobuf wire type {wire_type}")
        fields.append(ProtoField(number, wire_type, value))
    return fields


def unwrap_transport(payload: bytes) -> tuple[bytes, bytes]:
    """Split Narwal's framed common header from the command/response body."""
    if not payload or payload[0] != 1:
        raise ValueError("Invalid Narwal transport marker")
    header_size, body_start = read_varint(payload, 1)
    header_end = body_start + header_size
    if header_end > len(payload):
        raise ValueError("Truncated Narwal transport header")
    return payload[body_start:header_end], payload[header_end:]


def _values(
    fields: list[ProtoField], number: int, wire_type: int | None = None
) -> list[int | bytes]:
    return [
        item.value
        for item in fields
        if item.number == number
        and (wire_type is None or item.wire_type == wire_type)
    ]


def _integer(fields: list[ProtoField], number: int, default: int = 0) -> int:
    values = _values(fields, number, 0)
    return int(values[-1]) if values else default


def _message(fields: list[ProtoField], number: int) -> bytes:
    values = _values(fields, number, 2)
    return bytes(values[-1]) if values else b""


def _messages(fields: list[ProtoField], number: int) -> list[bytes]:
    return [bytes(value) for value in _values(fields, number, 2)]


def _signed(value: int, bits: int = 64) -> int:
    """Interpret protobuf int32/int64 values emitted as two's complement."""
    sign = 1 << (bits - 1)
    return value - (1 << bits) if value & sign else value


def _fixed32_float(fields: list[ProtoField], number: int) -> float:
    values = _values(fields, number, 5)
    if not values:
        return 0.0
    return float(struct.unpack("<f", bytes(values[-1]))[0])


def _pose(fields: list[ProtoField], number: int) -> NarwalPose | None:
    raw_pose = _message(fields, number)
    if not raw_pose:
        return None
    pose = decode_fields(raw_pose)
    point_raw = _message(pose, 1)
    if not point_raw:
        return None
    point = decode_fields(point_raw)
    return NarwalPose(
        x=_fixed32_float(point, 1),
        y=_fixed32_float(point, 2),
        angle=_fixed32_float(pose, 2),
    )


def parse_map_response(payload: bytes) -> NarwalMap:
    """Parse `/map/get_map/response` into a stable public model."""
    _, body = unwrap_transport(payload)
    response = decode_fields(body)
    if _integer(response, 1) != 1:
        raise ValueError("Narwal map request was not successful")
    map_fields = decode_fields(_message(response, 2))

    rooms: list[NarwalRoom] = []
    duplicate_names: dict[str, int] = {}
    for raw_room in _messages(map_fields, 12):
        room = decode_fields(raw_room)
        room_id = _integer(room, 1)
        room_type = _integer(room, 2)
        instance_index = _integer(room, 8)
        raw_name = _message(room, 3)
        name = raw_name.decode("utf-8", errors="replace").strip()
        if not name:
            name = ROOM_TYPE_NAMES.get(room_type, "Room")
            if instance_index > 1:
                name = f"{name} {instance_index}"
        duplicate_names[name] = duplicate_names.get(name, 0) + 1
        if duplicate_names[name] > 1:
            name = f"{name} {duplicate_names[name]}"
        if room_id:
            rooms.append(NarwalRoom(room_id, name, room_type, instance_index))

    border_fields = decode_fields(_message(map_fields, 6))
    border = (
        _signed(_integer(border_fields, 1)),
        _signed(_integer(border_fields, 2)),
        _signed(_integer(border_fields, 3)),
        _signed(_integer(border_fields, 4)),
    )

    return NarwalMap(
        revision=_integer(map_fields, 2),
        resolution=_integer(map_fields, 3),
        width=_integer(map_fields, 4),
        height=_integer(map_fields, 5),
        rooms=tuple(rooms),
        compressed_grid=_message(map_fields, 17),
        border=border,
        origin=_pose(map_fields, 7),
        station=_pose(map_fields, 8),
        robot_pose=_pose(map_fields, 24),
        robot_pose_update_time=_integer(map_fields, 36),
    )


def parse_clean_plans_response(payload: bytes) -> tuple[NarwalCleanPlan, ...]:
    """Parse official cleaning-plan room templates.

    Each field 2 item is a plan; its field 9 entries are the exact room
    messages accepted as field 3 by `/clean/easy_clean/start`.
    """
    _, body = unwrap_transport(payload)
    response = decode_fields(body)
    if _integer(response, 1) != 1:
        raise ValueError("Narwal cleaning-plan request was not successful")

    plans: list[NarwalCleanPlan] = []
    for raw_plan in _messages(response, 2):
        plan = decode_fields(raw_plan)
        templates: dict[int, bytes] = {}
        for room_template in _messages(plan, 9):
            room = decode_fields(room_template)
            room_id = _integer(room, 1)
            if room_id:
                templates[room_id] = room_template
        plans.append(
            NarwalCleanPlan(
                plan_id=_integer(plan, 1),
                mode=_integer(plan, 3),
                room_templates=templates,
            )
        )
    return tuple(plans)
