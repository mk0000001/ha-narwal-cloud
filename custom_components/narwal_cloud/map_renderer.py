"""Render the verified Narwal room grid as a PNG."""

from __future__ import annotations

import io
import json
import math
import zlib

from .protocol import NarwalMap, read_varint

ROOM_COLORS = (
    (104, 149, 238),
    (103, 196, 171),
    (244, 172, 183),
    (247, 190, 139),
    (174, 145, 214),
    (111, 190, 222),
    (237, 211, 109),
    (196, 150, 140),
)


def _pixels(compressed: bytes) -> list[int]:
    raw = zlib.decompress(compressed)
    position = 0
    if raw and raw[0] == 0x0A:
        _, position = read_varint(raw, 1)
    pixels: list[int] = []
    while position < len(raw):
        value, position = read_varint(raw, position)
        pixels.append(value)
    return pixels


def render_map(map_data: NarwalMap) -> bytes:
    """Render current cloud map data, rooms, station, and robot position."""
    from PIL import Image, ImageDraw, ImageFont

    if (
        not map_data.compressed_grid
        or map_data.width <= 0
        or map_data.height <= 0
    ):
        return b""
    values = _pixels(map_data.compressed_grid)
    expected = map_data.width * map_data.height
    values = (values + [0] * expected)[:expected]

    # Narwal's app presents this model's raw grid transposed.
    image = Image.new("RGB", (map_data.height, map_data.width), (34, 36, 43))
    image_pixels = image.load()
    sums: dict[int, list[int]] = {}
    for index, value in enumerate(values):
        x = index % map_data.width
        y = index // map_data.width
        if value in (0, 0x28):
            continue
        if value == 0x20:
            image_pixels[y, x] = (205, 207, 213)
            continue
        room_id = value >> 8
        pixel_type = value & 0xFF
        color = ROOM_COLORS[(room_id - 1) % len(ROOM_COLORS)]
        if pixel_type & 0x10:
            color = tuple(max(channel - 65, 0) for channel in color)
        else:
            stats = sums.setdefault(room_id, [0, 0, 0])
            stats[0] += x
            stats[1] += y
            stats[2] += 1
        image_pixels[y, x] = color

    image = image.resize(
        (map_data.height * 3, map_data.width * 3),
        Image.Resampling.NEAREST,
    )
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=14)
    for room in map_data.rooms:
        stats = sums.get(room.room_id)
        if not stats or not stats[2]:
            continue
        x = (stats[1] // stats[2]) * 3
        y = (stats[0] // stats[2]) * 3
        try:
            draw.text(
                (x, y),
                room.name,
                font=font,
                anchor="mm",
                fill="white",
                stroke_width=2,
                stroke_fill=(30, 30, 35),
            )
        except UnicodeEncodeError:
            # Pillow's bundled fallback font may not contain a custom
            # non-Latin room name; the room remains selectable in HA.
            pass

    marker = _pose_pixel(map_data)
    if marker is not None:
        raw_x, raw_y = marker
        x = raw_y * 3
        y = raw_x * 3
        radius = 9
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=(48, 116, 255),
            outline="white",
            width=3,
        )
        angle = (map_data.robot_pose.angle if map_data.robot_pose else 0.0)
        draw.line(
            (
                x,
                y,
                x + math.cos(angle) * radius,
                y + math.sin(angle) * radius,
            ),
            fill="white",
            width=3,
        )

    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def calibration_points(map_data: NarwalMap) -> list[dict[str, dict[str, int]]]:
    """Return the same three-point calibration structure used by Dreame."""
    points = []
    for x, y in ((0, 0), (1000, 0), (0, 1000)):
        image_point = _relative_pose_pixel(map_data, x, y)
        points.append(
            {
                "vacuum": {"x": x, "y": y},
                "map": {
                    "x": round(image_point[1] * 3) if image_point else 0,
                    "y": round(image_point[0] * 3) if image_point else 0,
                },
            }
        )
    return points


def map_attributes(map_data: NarwalMap) -> dict:
    """Expose Dreame-compatible map attributes for vacuum map cards."""
    robot = _relative_robot_position(map_data)
    rooms = {
        room.room_id: {
            "room_id": room.room_id,
            "name": room.name,
            "type": room.room_type,
            "index": room.instance_index,
        }
        for room in map_data.rooms
    }
    attributes: dict = {
        "map_id": map_data.revision,
        "frame_id": map_data.robot_pose_update_time or map_data.revision,
        "rotation": 0,
        "rooms": rooms,
        "is_empty": not bool(map_data.compressed_grid),
        "calibration_points": calibration_points(map_data),
    }
    if robot is not None:
        attributes["robot_position"] = {
            "x": robot[0],
            "y": robot[1],
            "a": round(math.degrees(map_data.robot_pose.angle)) % 360,
        }
    if map_data.station is not None:
        attributes["charger_position"] = {"x": 0, "y": 0, "a": 0}
    return attributes


def render_map_data(map_data: NarwalMap) -> bytes:
    """Render a Dreame/Valetudo-compatible PNG map-data payload.

    Dreame's ``map_data`` camera is still an image/png entity. Its PNG embeds
    live ValetudoMap JSON in the compressed ``ValetudoMap`` text chunk.
    """
    from PIL import Image, PngImagePlugin

    layers: list[dict] = []
    entities: list[dict] = []
    pixel_size = max(1, round(map_data.resolution / 10))
    size = 6553
    offset_x = round((size - map_data.height) / 2)
    offset_y = round((size + map_data.width) / 2)

    if map_data.compressed_grid and map_data.width > 0 and map_data.height > 0:
        values = _pixels(map_data.compressed_grid)
        expected = map_data.width * map_data.height
        values = (values + [0] * expected)[:expected]
        grouped: dict[tuple[str, int], list[tuple[int, int]]] = {}
        for index, value in enumerate(values):
            raw_x = index % map_data.width
            raw_y = index // map_data.width
            if value in (0, 0x28):
                continue
            if value == 0x20:
                key = ("wall", 0)
            else:
                room_id = value >> 8
                key = ("segment" if room_id else "floor", room_id)
            grouped.setdefault(key, []).append(
                (offset_x + raw_y, offset_y - raw_x)
            )

        room_names = {room.room_id: room.name for room in map_data.rooms}
        for (layer_type, room_id), pixels in grouped.items():
            pixels.sort(key=lambda point: (point[1], point[0]))
            flat = [coordinate for point in pixels for coordinate in point]
            xs = flat[0::2]
            ys = flat[1::2]
            compressed: list[int] = []
            start_x = current_y = count = None
            for x, y in pixels:
                if current_y != y or start_x is None or x > start_x + count:
                    if start_x is not None:
                        compressed.extend((start_x, current_y, count))
                    start_x, current_y, count = x, y, 1
                elif x != start_x:
                    count += 1
            if start_x is not None:
                compressed.extend((start_x, current_y, count))
            layer = {
                "type": layer_type,
                "pixels": [],
                "compressedPixels": compressed,
                "dimensions": {
                    "x": {
                        "min": min(xs), "max": max(xs),
                        "mid": round((min(xs) + max(xs)) / 2),
                        "avg": round(sum(xs) / len(xs)),
                    },
                    "y": {
                        "min": min(ys), "max": max(ys),
                        "mid": round((min(ys) + max(ys)) / 2),
                        "avg": round(sum(ys) / len(ys)),
                    },
                    "pixelCount": len(pixels),
                },
            }
            if layer_type == "segment":
                layer["metaData"] = {
                    "segmentId": room_id,
                    "active": False,
                    "name": room_names.get(room_id, f"Room {room_id}"),
                }
            layers.append(layer)

    marker = _pose_pixel(map_data)
    if marker is not None:
        entities.append(
            {
                "type": "robot_position",
                "points": [
                    round((offset_x + marker[1]) * pixel_size),
                    round((offset_y - marker[0]) * pixel_size),
                ],
                "metaData": {
                    "angle": round(math.degrees(map_data.robot_pose.angle)) % 360
                },
            }
        )
    station_marker = _relative_pose_pixel(map_data, 0, 0)
    if station_marker is not None:
        entities.append(
            {
                "type": "charger_location",
                "points": [
                    round((offset_x + station_marker[1]) * pixel_size),
                    round((offset_y - station_marker[0]) * pixel_size),
                ],
                "metaData": {"angle": 0},
            }
        )

    payload = {
        "__class": "ValetudoMap",
        "size": {"x": size, "y": size},
        "pixelSize": pixel_size,
        "layers": layers,
        "entities": entities,
        "metaData": {"version": 2, "rotation": 0},
    }
    image = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text(
        "ValetudoMap", json.dumps(payload, separators=(",", ":")), zip=True
    )
    output = io.BytesIO()
    image.save(output, "PNG", pnginfo=metadata)
    return output.getvalue()


def _pose_pixel(map_data: NarwalMap) -> tuple[float, float] | None:
    """Convert Narwal's live pose to this model's raw grid coordinates.

    The app anchors the station at the origin-aligned pixel and applies
    robot-vs-station deltas in the origin frame.
    """
    if not map_data.origin or not map_data.station or not map_data.robot_pose:
        return None
    minimum_x, _, minimum_y, _ = map_data.border
    base_x = map_data.origin.y * 10 - minimum_y
    base_y = map_data.origin.x * 10 - minimum_x
    resolution = map_data.resolution / 1000
    if resolution <= 0:
        return None

    delta_x = map_data.robot_pose.x - map_data.station.x
    delta_y = map_data.robot_pose.y - map_data.station.y
    cosine = math.cos(-map_data.origin.angle)
    sine = math.sin(-map_data.origin.angle)
    local_x = delta_x * cosine - delta_y * sine
    local_y = delta_x * sine + delta_y * cosine
    raw_x = base_x + local_y / resolution
    raw_y = base_y + local_x / resolution
    if not (0 <= raw_x < map_data.width and 0 <= raw_y < map_data.height):
        return None
    return raw_x, raw_y


def _relative_pose_pixel(
    map_data: NarwalMap, x_mm: float, y_mm: float
) -> tuple[float, float] | None:
    """Convert station-relative millimetres to raw map pixels."""
    if not map_data.origin or not map_data.station:
        return None
    minimum_x, _, minimum_y, _ = map_data.border
    base_x = map_data.origin.y * 10 - minimum_y
    base_y = map_data.origin.x * 10 - minimum_x
    resolution = map_data.resolution / 1000
    if resolution <= 0:
        return None
    delta_x = x_mm / 1000
    delta_y = y_mm / 1000
    cosine = math.cos(-map_data.origin.angle)
    sine = math.sin(-map_data.origin.angle)
    local_x = delta_x * cosine - delta_y * sine
    local_y = delta_x * sine + delta_y * cosine
    return base_x + local_y / resolution, base_y + local_x / resolution


def _relative_robot_position(map_data: NarwalMap) -> tuple[int, int] | None:
    """Return robot coordinates in millimetres relative to the station."""
    if not map_data.robot_pose or not map_data.station:
        return None
    return (
        round((map_data.robot_pose.x - map_data.station.x) * 1000),
        round((map_data.robot_pose.y - map_data.station.y) * 1000),
    )
