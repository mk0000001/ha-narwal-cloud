"""Minimal MQTT 5 command transport for Narwal Cloud."""

from __future__ import annotations

import asyncio
import ssl
import uuid
from urllib.parse import urlparse


class NarwalMqttError(Exception):
    """The Narwal broker rejected or failed a command connection."""


def _varint(value: int) -> bytes:
    output = bytearray()
    while True:
        encoded = value % 128
        value //= 128
        if value:
            encoded |= 0x80
        output.append(encoded)
        if not value:
            return bytes(output)


def _field(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(2, "big") + encoded


def _protobuf_string(field_number: int, value: str) -> bytes:
    encoded = value.encode("utf-8")
    return _varint((field_number << 3) | 2) + _varint(len(encoded)) + encoded


def _protobuf_varint(field_number: int, value: int) -> bytes:
    return _varint(field_number << 3) + _varint(value)


def _protobuf_message(field_number: int, value: bytes) -> bytes:
    return _varint((field_number << 3) | 2) + _varint(len(value)) + value


def _task_payload(
    client_uuid: str,
    response_topic: str,
    command_body: bytes = b"",
) -> bytes:
    response = (
        _protobuf_string(1, response_topic)
        + _protobuf_string(2, str(uuid.uuid4()))
    )
    protobuf = (
        _protobuf_string(1, client_uuid)
        + _protobuf_string(2, client_uuid)
        + _varint((5 << 3) | 2)
        + _varint(len(response))
        + response
    )
    # Narwal frames the common request header, then appends the command-specific
    # protobuf body outside that declared header length.
    return b"\x01" + _varint(len(protobuf)) + protobuf + command_body


def _easy_clean_body(
    room_ids: list[int],
    mode: int = 1,
    suction: int = 2,
    humidity: int = 2,
    cycles: int = 1,
) -> bytes:
    """Build a room plan using fields verified against all five app modes."""
    if mode not in range(1, 6):
        raise ValueError(f"Unsupported Narwal cleaning mode: {mode}")
    if suction not in range(1, 4) or humidity not in range(1, 4):
        raise ValueError("Narwal suction and humidity must be between 1 and 3")
    if cycles not in range(1, 4):
        raise ValueError("Narwal cleaning cycles must be between 1 and 3")

    body = _protobuf_varint(1, mode) + _protobuf_varint(2, 1)
    for room_id in room_ids:
        room = _protobuf_varint(1, room_id)
        if mode == 1:
            settings = (
                _protobuf_varint(1, 2)
                + _protobuf_varint(2, 1)
                + _protobuf_varint(3, 2)
                + _protobuf_varint(4, 1)
            )
            room += _protobuf_varint(2, 3) + _protobuf_message(6, settings)
        elif mode == 2:
            settings = _protobuf_varint(1, suction) + _protobuf_varint(2, cycles)
            room += _protobuf_varint(2, 1) + _protobuf_message(4, settings)
        elif mode == 3:
            settings = (
                _protobuf_varint(1, 1)
                + _protobuf_varint(2, cycles)
                + _protobuf_varint(3, humidity)
            )
            room += _protobuf_varint(2, 1) + _protobuf_message(5, settings)
        elif mode == 4:
            settings = (
                _protobuf_varint(1, suction)
                + _protobuf_varint(2, cycles)
                + _protobuf_varint(3, humidity)
                + _protobuf_varint(4, cycles)
            )
            room += _protobuf_varint(2, 1) + _protobuf_message(6, settings)
        else:
            vacuum = (
                _protobuf_varint(1, suction) + _protobuf_varint(2, cycles)
            )
            mop = (
                _protobuf_varint(1, 1)
                + _protobuf_varint(2, cycles)
                + _protobuf_varint(3, humidity)
            )
            settings = _protobuf_message(1, vacuum) + _protobuf_message(2, mop)
            room += _protobuf_varint(2, 1) + _protobuf_message(7, settings)
        body += _protobuf_message(3, room)
    return body


def _force_end_body() -> bytes:
    """Build the task termination body captured from the official app."""
    return _protobuf_message(2, b"\x01\x02")


def _active_robot_body() -> bytes:
    """Build the Freo activation body captured from the official app."""
    return (
        _protobuf_message(
            1,
            _protobuf_varint(1, 10000)
            + _protobuf_varint(2, 10000)
            + _protobuf_varint(3, 10000)
            + _protobuf_varint(8, 0),
        )
        + _protobuf_varint(2, 60000)
        + _protobuf_varint(3, 0)
    )


async def _read_varint(reader: asyncio.StreamReader) -> int:
    value = 0
    multiplier = 1
    for _ in range(4):
        encoded = (await reader.readexactly(1))[0]
        value += (encoded & 0x7F) * multiplier
        if not encoded & 0x80:
            return value
        multiplier *= 128
    raise NarwalMqttError("Narwal returned an invalid MQTT packet")


def _mqtt_publish_payload(packet_body: bytes) -> bytes:
    """Extract the application payload from an MQTT 5 PUBLISH packet body."""
    if len(packet_body) < 3:
        raise NarwalMqttError("Narwal returned a truncated MQTT response")
    topic_size = int.from_bytes(packet_body[:2], "big")
    position = 2 + topic_size
    if position >= len(packet_body):
        raise NarwalMqttError("Narwal returned an invalid MQTT response topic")

    # All requests and responses used here are QoS 0, so there is no packet ID.
    property_size = 0
    multiplier = 1
    for _ in range(4):
        if position >= len(packet_body):
            raise NarwalMqttError("Narwal returned invalid MQTT properties")
        encoded = packet_body[position]
        position += 1
        property_size += (encoded & 0x7F) * multiplier
        if not encoded & 0x80:
            break
        multiplier *= 128
    else:
        raise NarwalMqttError("Narwal returned invalid MQTT properties")
    position += property_size
    if position > len(packet_body):
        raise NarwalMqttError("Narwal returned truncated MQTT properties")
    return packet_body[position:]


def _mqtt_publish_topic(packet_body: bytes) -> str:
    """Extract a PUBLISH topic so interleaved responses can be ignored."""
    if len(packet_body) < 2:
        return ""
    topic_size = int.from_bytes(packet_body[:2], "big")
    if len(packet_body) < 2 + topic_size:
        return ""
    return packet_body[2 : 2 + topic_size].decode("utf-8", errors="replace")


async def _async_request_once(
    broker_url: str,
    access_token: str,
    client_uuid: str,
    product_id: str,
    device_id: str,
    topic_suffix: str,
    command_body: bytes = b"",
    *,
    response_required: bool = True,
) -> bytes:
    """Publish one request and return its matching response payload."""
    responses = await _async_request_sequence(
        broker_url,
        access_token,
        client_uuid,
        product_id,
        device_id,
        ((topic_suffix, command_body, response_required),),
    )
    return responses[0]


async def _async_request_sequence(
    broker_url: str,
    access_token: str,
    client_uuid: str,
    product_id: str,
    device_id: str,
    requests: tuple[tuple[str, bytes, bool], ...],
) -> tuple[bytes, ...]:
    """Publish requests in order over one MQTT session."""
    parsed = urlparse(broker_url)
    host = parsed.hostname
    if not host:
        raise NarwalMqttError("Narwal returned an invalid broker address")
    port = parsed.port or 8883
    client_id = f"app_{client_uuid}_{uuid.uuid4()}"

    connect_variable = (
        _field("MQTT")
        + bytes([5, 0xC2])
        + (30).to_bytes(2, "big")
        + b"\x00"
    )
    connect_payload = (
        _field(client_id) + _field(client_uuid) + _field(access_token)
    )
    connect_body = connect_variable + connect_payload
    connect_packet = b"\x10" + _varint(len(connect_body)) + connect_body

    context = ssl.create_default_context()
    writer: asyncio.StreamWriter | None = None
    stage = "connect"
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                host,
                port,
                ssl=context,
                server_hostname=host,
            ),
            timeout=15,
        )
        writer.write(connect_packet)
        await writer.drain()
        stage = "CONNACK header"
        packet_type = (await asyncio.wait_for(reader.readexactly(1), timeout=15))[0] >> 4
        remaining = await asyncio.wait_for(_read_varint(reader), timeout=15)
        stage = "CONNACK body"
        body = await asyncio.wait_for(reader.readexactly(remaining), timeout=15)
        if packet_type != 2 or len(body) < 2 or body[1] != 0:
            raise NarwalMqttError("Narwal rejected the MQTT session")

        # The official app establishes these broadcast subscriptions before
        # activating the robot. Older Freo firmware does not answer get_map
        # unless this receiving session has advertised the live map/status
        # topics first.
        broadcast_suffixes = (
            "status/robot_base_status",
            "status/working_status",
            "upgrade/upgrade_status",
            "status/download_status",
            "map/display_map",
            "status/time_line_status",
            "status/point_navi_plan_traj",
            "developer/planning_debug_info",
        )
        broadcast_subscribe_body = b"\xff\xfe\x00" + b"".join(
            _field(f"/{product_id}/{device_id}/{suffix}") + b"\x00"
            for suffix in broadcast_suffixes
        )
        broadcast_subscribe_packet = (
            b"\x82"
            + _varint(len(broadcast_subscribe_body))
            + broadcast_subscribe_body
        )
        writer.write(broadcast_subscribe_packet)
        await writer.drain()
        stage = "broadcast SUBACK header"
        packet_type = (
            await asyncio.wait_for(reader.readexactly(1), timeout=15)
        )[0] >> 4
        remaining = await asyncio.wait_for(_read_varint(reader), timeout=15)
        stage = "broadcast SUBACK body"
        await asyncio.wait_for(reader.readexactly(remaining), timeout=15)
        if packet_type != 9:
            raise NarwalMqttError(
                "Narwal rejected the broadcast subscriptions"
            )

        responses: list[bytes] = []
        for packet_id, (topic_suffix, command_body, response_required) in enumerate(
            requests, start=1
        ):
            topic = f"/{product_id}/{device_id}/{topic_suffix}"
            if topic_suffix == "common/notify_app_event":
                response_topic = (
                    f"/{product_id}/{device_id}/general/service/response"
                )
            else:
                response_topic = (
                    f"{topic}/response" if response_required else ""
                )
            command_payload = _task_payload(
                client_uuid, response_topic, command_body
            )
            publish_body = _field(topic) + b"\x00" + command_payload
            publish_packet = (
                b"\x30" + _varint(len(publish_body)) + publish_body
            )

            # The official app subscribes to each response topic before
            # publishing. Keeping activation and map/plan requests on this
            # same connection is required by older Freo cloud firmware.
            if response_required:
                subscribe_body = (
                    packet_id.to_bytes(2, "big")
                    + b"\x00"
                    + _field(response_topic)
                    + b"\x00"
                )
                subscribe_packet = (
                    b"\x82" + _varint(len(subscribe_body)) + subscribe_body
                )
                writer.write(subscribe_packet)
                await writer.drain()
                stage = f"{topic_suffix} SUBACK header"
                while True:
                    packet_type = (
                        await asyncio.wait_for(
                            reader.readexactly(1), timeout=15
                        )
                    )[0] >> 4
                    remaining = await asyncio.wait_for(
                        _read_varint(reader), timeout=15
                    )
                    stage = f"{topic_suffix} SUBACK body"
                    await asyncio.wait_for(
                        reader.readexactly(remaining), timeout=15
                    )
                    if packet_type == 9:
                        break

            writer.write(publish_packet)
            await writer.drain()
            if not response_required:
                responses.append(b"")
                continue
            # The activation response is asynchronous in the official app.
            # Its subscription must remain active, but waiting here can
            # deadlock older Freo firmware before the map request is sent.
            if topic_suffix in {
                "common/active_robot_publish",
                "common/notify_app_event",
                "status/get_device_base_status",
            }:
                responses.append(b"")
                if topic_suffix == "common/active_robot_publish":
                    # Captures show roughly 0.6-0.8 s before the app sends its
                    # wake/read burst. The activation response itself remains
                    # asynchronous and may arrive between later SUBACKs.
                    await asyncio.sleep(1)
                continue
            stage = f"{topic_suffix} response header"
            while True:
                packet_type = (
                    await asyncio.wait_for(
                        reader.readexactly(1), timeout=15
                    )
                )[0] >> 4
                remaining = await asyncio.wait_for(
                    _read_varint(reader), timeout=15
                )
                stage = f"{topic_suffix} response body"
                response_packet = await asyncio.wait_for(
                    reader.readexactly(remaining), timeout=15
                )
                if (
                    packet_type == 3
                    and _mqtt_publish_topic(response_packet) == response_topic
                ):
                    break
            responses.append(_mqtt_publish_payload(response_packet))

        return tuple(responses)
    except (OSError, TimeoutError, asyncio.IncompleteReadError) as err:
        raise NarwalMqttError(
            f"Unable to send the Narwal command during {stage}"
        ) from err
    finally:
        if writer is not None:
            try:
                writer.write(b"\xE0\x00")
                await writer.drain()
            except (OSError, ConnectionError):
                pass
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, ConnectionError):
                pass


async def async_request(
    broker_url: str,
    access_token: str,
    client_uuid: str,
    product_id: str,
    device_id: str,
    topic_suffix: str,
    command_body: bytes = b"",
    *,
    activate_robot: bool = False,
    response_required: bool = True,
) -> bytes:
    """Send a request, optionally activating app-style robot publishing first."""
    if activate_robot:
        responses = await _async_request_sequence(
            broker_url,
            access_token,
            client_uuid,
            product_id,
            device_id,
            (
                (
                    "common/active_robot_publish",
                    _active_robot_body(),
                    True,
                ),
                ("common/notify_app_event", b"\x08\x01", True),
                ("status/get_device_base_status", b"", True),
                (topic_suffix, command_body, response_required),
            ),
        )
        return responses[-1]
    return await _async_request_once(
        broker_url,
        access_token,
        client_uuid,
        product_id,
        device_id,
        topic_suffix,
        command_body,
        response_required=response_required,
    )


async def async_publish_task_command(
    broker_url: str,
    access_token: str,
    client_uuid: str,
    product_id: str,
    device_id: str,
    action: str,
    room_ids: list[int] | None = None,
    *,
    mode: int = 1,
    suction: int = 2,
    humidity: int = 2,
    cycles: int = 1,
) -> None:
    """Publish one captured task command using a short-lived MQTT session."""
    if action not in {
        "pause",
        "resume",
        "easy_clean_start",
        "force_end",
        "recall",
        "wash_and_dry_mop",
        "finish_station",
    }:
        raise ValueError(f"Unsupported Narwal task action: {action}")

    if action == "easy_clean_start":
        topic_suffix = "clean/easy_clean/start"
        command_body = _easy_clean_body(
            room_ids or [], mode, suction, humidity, cycles
        )
    elif action == "force_end":
        topic_suffix = "task/force_end"
        command_body = _force_end_body()
    elif action == "recall":
        topic_suffix = "supply/recall"
        command_body = b""
    elif action == "wash_and_dry_mop":
        topic_suffix = "supply/wash_and_dry_mop"
        command_body = b""
    elif action == "finish_station":
        topic_suffix = "task/force_end"
        command_body = b""
    else:
        topic_suffix = f"task/{action}"
        command_body = b""
    await async_request(
        broker_url,
        access_token,
        client_uuid,
        product_id,
        device_id,
        topic_suffix,
        command_body,
        response_required=action != "finish_station",
    )
