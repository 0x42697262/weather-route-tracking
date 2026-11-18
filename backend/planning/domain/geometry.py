"""Pure geometry on WGS84 route lines: distances, positions along a line, simplification,
encoded polylines, sideways offsets and ferry intervals. Distances are in km unless named."""

import math
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from planning.constants import (
    EARTH_RADIUS_KM,
    FULL_TURN_DEG,
    KM_PER_DEGREE,
    MAX_LATITUDE_DEG,
    MAX_LONGITUDE_DEG,
    METERS_PER_KM,
    MIN_LATITUDE_COSINE,
    OFFSET_DIRECTION_WINDOW_KM,
    POINTS_PER_SEGMENT,
    POLYLINE_CHARACTER_OFFSET,
    POLYLINE_CHUNK_BITS,
    POLYLINE_CHUNK_MASK,
    POLYLINE_CONTINUATION_BIT,
    POLYLINE_FACTOR,
    POLYLINE_MAX_CHARACTER,
    POLYLINE_MAX_CHUNKS_PER_VALUE,
    QUARTER_TURN_DEG,
    ROUTE_SIMPLIFY_TOLERANCE_M,
    SIMPLIFY_WINDOW_POINTS,
    VALUES_PER_COORDINATE,
)
from planning.domain.values import Coordinate, PointRange
from planning.errors import ErrorCode, PlanningError


class PolylineInvalid(PlanningError):
    """An encoded polyline is truncated, holds a character outside the encoding, or decodes to a
    position outside the valid latitude and longitude ranges."""

    code = ErrorCode.INVALID_REQUEST


class DegenerateLine(ValueError):
    """A line has no length where a direction along it is needed."""


class Side(StrEnum):
    """A side of a line, looking in its direction of travel."""

    LEFT = "left"
    RIGHT = "right"


SIDE_TURN_DEG = MappingProxyType({Side.LEFT: -QUARTER_TURN_DEG, Side.RIGHT: QUARTER_TURN_DEG})


@dataclass(frozen=True, slots=True)
class RouteLine:
    """A line and the cumulative great-circle km at each of its points (first is 0)."""

    points: tuple[Coordinate, ...]
    cumulative_km: tuple[float, ...]

    @property
    def length_km(self) -> float:
        """Total length; 0 for a line with fewer than two points."""
        return self.cumulative_km[-1] if self.cumulative_km else 0.0


@dataclass(frozen=True, slots=True)
class KmInterval:
    """A closed interval of km positions along a line, `start_km <= end_km`."""

    start_km: float
    end_km: float

    def contains(self, distance_km: float) -> bool:
        """Whether the position lies in the interval, ends included."""
        return self.start_km <= distance_km <= self.end_km


def haversine_km(start: Coordinate, end: Coordinate) -> float:
    """Great-circle distance between two positions."""
    start_lat = math.radians(start.latitude)
    end_lat = math.radians(end.latitude)
    half_dlat = (end_lat - start_lat) / 2
    half_dlon = math.radians(end.longitude - start.longitude) / 2
    chord = math.sin(half_dlat) ** 2 + math.cos(start_lat) * math.cos(end_lat) * (
        math.sin(half_dlon) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(chord)))


def measure_line(points: Sequence[Coordinate]) -> RouteLine:
    """The line with its cumulative km, summing great-circle distances between points."""
    cumulative = [0.0] * len(points)
    total_km = 0.0
    for index in range(1, len(points)):
        total_km += haversine_km(points[index - 1], points[index])
        cumulative[index] = total_km
    return RouteLine(points=tuple(points), cumulative_km=tuple(cumulative))


def km_at_index(line: RouteLine, point_index: int) -> float:
    """The km position of a point, the index clamped to the line."""
    return line.cumulative_km[max(0, min(point_index, len(line.cumulative_km) - 1))]


def point_at_km(line: RouteLine, distance_km: float) -> Coordinate:
    """The position at `distance_km` along the line, interpolated on its segment.

    Positions before the start or past the end are clamped to the first or last point.
    """
    cumulative = line.cumulative_km
    if distance_km <= 0 or len(cumulative) == 1:
        return line.points[0]
    if distance_km >= cumulative[-1]:
        return line.points[-1]
    end_index = bisect_right(cumulative, distance_km)
    start_index = end_index - 1
    segment_km = cumulative[end_index] - cumulative[start_index]
    share = (distance_km - cumulative[start_index]) / segment_km if segment_km > 0 else 0.0
    start = line.points[start_index]
    end = line.points[end_index]
    return Coordinate(
        latitude=start.latitude + (end.latitude - start.latitude) * share,
        longitude=start.longitude + (end.longitude - start.longitude) * share,
    )


def longitude_km_per_degree(latitude_deg: float) -> float:
    """Km per degree of longitude at a latitude, bounded away from zero near the poles."""
    return KM_PER_DEGREE * max(math.cos(math.radians(latitude_deg)), MIN_LATITUDE_COSINE)


def segment_distance_km(point: Coordinate, start: Coordinate, end: Coordinate) -> float:
    """Distance from a point to a segment, on a local equirectangular projection at the point.

    Accurate to well under 1% for segments and distances up to tens of km.
    """
    scale_x = longitude_km_per_degree(point.latitude)
    start_x = (start.longitude - point.longitude) * scale_x
    start_y = (start.latitude - point.latitude) * KM_PER_DEGREE
    delta_x = (end.longitude - start.longitude) * scale_x
    delta_y = (end.latitude - start.latitude) * KM_PER_DEGREE
    length_sq = delta_x * delta_x + delta_y * delta_y
    if length_sq == 0:
        return math.hypot(start_x, start_y)
    share = max(0.0, min(1.0, -(start_x * delta_x + start_y * delta_y) / length_sq))
    return math.hypot(start_x + share * delta_x, start_y + share * delta_y)


def simplify_indexes(
    points: Sequence[Coordinate], tolerance_m: float = ROUTE_SIMPLIFY_TOLERANCE_M
) -> tuple[int, ...]:
    """Douglas-Peucker simplification; the ascending indexes of the points kept.

    Both endpoints are always kept, and every removed point lies within `tolerance_m` of the
    simplified segment that replaces it. Iterative, so long lines need no deep recursion. The
    line is simplified in windows of `SIMPLIFY_WINDOW_POINTS` whose boundary points are kept,
    which bounds the worst case to linear time in the number of points.
    """
    count = len(points)
    if count <= POINTS_PER_SEGMENT:
        return tuple(range(count))
    tolerance_km = tolerance_m / METERS_PER_KM
    latitudes = [point.latitude for point in points]
    longitudes = [point.longitude for point in points]
    keep = [False] * count
    pending: list[tuple[int, int]] = []
    for window_start in range(0, count - 1, SIMPLIFY_WINDOW_POINTS):
        window_end = min(window_start + SIMPLIFY_WINDOW_POINTS, count - 1)
        keep[window_start] = keep[window_end] = True
        pending.append((window_start, window_end))
    while pending:
        first, last = pending.pop()
        if last - first < POINTS_PER_SEGMENT:
            continue
        farthest_index, farthest_km = _farthest_from_chord(latitudes, longitudes, first, last)
        if farthest_km > tolerance_km:
            keep[farthest_index] = True
            pending.append((first, farthest_index))
            pending.append((farthest_index, last))
    return tuple(index for index, kept in enumerate(keep) if kept)


def _farthest_from_chord(
    latitudes: list[float], longitudes: list[float], first: int, last: int
) -> tuple[int, float]:
    origin_lat = latitudes[first]
    origin_lon = longitudes[first]
    scale_x = longitude_km_per_degree((origin_lat + latitudes[last]) / 2)
    chord_x = (longitudes[last] - origin_lon) * scale_x
    chord_y = (latitudes[last] - origin_lat) * KM_PER_DEGREE
    length_sq = chord_x * chord_x + chord_y * chord_y
    farthest_index = first + 1
    farthest_sq = -1.0
    for index in range(first + 1, last):
        point_x = (longitudes[index] - origin_lon) * scale_x
        point_y = (latitudes[index] - origin_lat) * KM_PER_DEGREE
        if length_sq > 0:
            share = max(0.0, min(1.0, (point_x * chord_x + point_y * chord_y) / length_sq))
            point_x -= share * chord_x
            point_y -= share * chord_y
        distance_sq = point_x * point_x + point_y * point_y
        if distance_sq > farthest_sq:
            farthest_sq = distance_sq
            farthest_index = index
    return farthest_index, math.sqrt(farthest_sq)


def encode_polyline(points: Sequence[Coordinate]) -> str:
    """Google encoded polyline at precision 5."""
    characters: list[str] = []
    previous_lat = 0
    previous_lon = 0
    for point in points:
        scaled_lat = round(point.latitude * POLYLINE_FACTOR)
        scaled_lon = round(point.longitude * POLYLINE_FACTOR)
        _encode_value(scaled_lat - previous_lat, characters)
        _encode_value(scaled_lon - previous_lon, characters)
        previous_lat = scaled_lat
        previous_lon = scaled_lon
    return "".join(characters)


def _encode_value(value: int, characters: list[str]) -> None:
    remaining = ~(value << 1) if value < 0 else value << 1
    while remaining >= POLYLINE_CONTINUATION_BIT:
        chunk = POLYLINE_CONTINUATION_BIT | (remaining & POLYLINE_CHUNK_MASK)
        characters.append(chr(chunk + POLYLINE_CHARACTER_OFFSET))
        remaining >>= POLYLINE_CHUNK_BITS
    characters.append(chr(remaining + POLYLINE_CHARACTER_OFFSET))


def decode_polyline(encoded: str) -> tuple[Coordinate, ...]:
    """Decode a Google encoded polyline at precision 5.

    Raises:
        PolylineInvalid: the text is truncated, holds a character outside the encoding, or a
            position is outside latitude +-90 or longitude +-180.
    """
    values: list[int] = []
    position = 0
    while position < len(encoded):
        value, position = _decode_value(encoded, position)
        values.append(value)
    if len(values) % VALUES_PER_COORDINATE:
        raise PolylineInvalid
    points: list[Coordinate] = []
    scaled_lat = 0
    scaled_lon = 0
    for value_index in range(0, len(values), VALUES_PER_COORDINATE):
        scaled_lat += values[value_index]
        scaled_lon += values[value_index + 1]
        latitude = scaled_lat / POLYLINE_FACTOR
        longitude = scaled_lon / POLYLINE_FACTOR
        if abs(latitude) > MAX_LATITUDE_DEG or abs(longitude) > MAX_LONGITUDE_DEG:
            raise PolylineInvalid
        points.append(Coordinate(latitude=latitude, longitude=longitude))
    return tuple(points)


def _decode_value(encoded: str, position: int) -> tuple[int, int]:
    result = 0
    for chunk_number in range(POLYLINE_MAX_CHUNKS_PER_VALUE):
        if position >= len(encoded):
            raise PolylineInvalid
        character_code = ord(encoded[position])
        if not POLYLINE_CHARACTER_OFFSET <= character_code <= POLYLINE_MAX_CHARACTER:
            raise PolylineInvalid
        position += 1
        chunk = character_code - POLYLINE_CHARACTER_OFFSET
        result |= (chunk & POLYLINE_CHUNK_MASK) << (chunk_number * POLYLINE_CHUNK_BITS)
        if chunk < POLYLINE_CONTINUATION_BIT:
            return (~(result >> 1) if result & 1 else result >> 1), position
    raise PolylineInvalid


def initial_bearing_deg(start: Coordinate, end: Coordinate) -> float:
    """Great-circle initial bearing from `start` to `end`, clockwise from north, in [0, 360)."""
    start_lat = math.radians(start.latitude)
    end_lat = math.radians(end.latitude)
    delta_lon = math.radians(end.longitude - start.longitude)
    east = math.sin(delta_lon) * math.cos(end_lat)
    north = math.cos(start_lat) * math.sin(end_lat) - math.sin(start_lat) * math.cos(
        end_lat
    ) * math.cos(delta_lon)
    return math.degrees(math.atan2(east, north)) % FULL_TURN_DEG


def destination_point(start: Coordinate, bearing_deg: float, distance_km: float) -> Coordinate:
    """The position `distance_km` from `start` along a great circle at `bearing_deg`."""
    start_lat = math.radians(start.latitude)
    start_lon = math.radians(start.longitude)
    bearing = math.radians(bearing_deg)
    angular = distance_km / EARTH_RADIUS_KM
    end_lat = math.asin(
        math.sin(start_lat) * math.cos(angular)
        + math.cos(start_lat) * math.sin(angular) * math.cos(bearing)
    )
    end_lon = start_lon + math.atan2(
        math.sin(bearing) * math.sin(angular) * math.cos(start_lat),
        math.cos(angular) - math.sin(start_lat) * math.sin(end_lat),
    )
    longitude = (math.degrees(end_lon) + MAX_LONGITUDE_DEG) % FULL_TURN_DEG - MAX_LONGITUDE_DEG
    return Coordinate(latitude=math.degrees(end_lat), longitude=longitude)


def offset_point(line: RouteLine, distance_km: float, offset_km: float, side: Side) -> Coordinate:
    """A point `offset_km` to one side of the line, perpendicular to it at `distance_km`.

    The line's direction is taken between the positions `OFFSET_DIRECTION_WINDOW_KM` before and
    after, clamped to the line, so a single short segment does not decide it.

    Raises:
        DegenerateLine: the line has no length around `distance_km`.
    """
    before = point_at_km(line, distance_km - OFFSET_DIRECTION_WINDOW_KM)
    after = point_at_km(line, distance_km + OFFSET_DIRECTION_WINDOW_KM)
    if before == after:
        raise DegenerateLine
    bearing_deg = initial_bearing_deg(before, after) + SIDE_TURN_DEG[side]
    return destination_point(point_at_km(line, distance_km), bearing_deg, offset_km)


def ferry_intervals_km(line: RouteLine, sections: Sequence[PointRange]) -> tuple[KmInterval, ...]:
    """The km intervals of ferry sections given as point index ranges, in the order given."""
    intervals: list[KmInterval] = []
    for section in sections:
        start_km = km_at_index(line, section.start_index)
        end_km = km_at_index(line, section.end_index)
        intervals.append(KmInterval(start_km=min(start_km, end_km), end_km=max(start_km, end_km)))
    return tuple(intervals)
