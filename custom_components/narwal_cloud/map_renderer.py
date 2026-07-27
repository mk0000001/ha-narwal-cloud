"""Render the verified Narwal room grid as a PNG."""

from __future__ import annotations

import io
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
