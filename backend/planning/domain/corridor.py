"""The heatmap corridor: weather grid cells around the route lines (`docs/trip-planning.md`,
"Heatmap grid")."""

import itertools
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from planning.constants import (
    CORRIDOR_AMBIGUITY_TOLERANCE_FACTOR,
    CORRIDOR_BUFFER_KM,
    CORRIDOR_CELL_GROWTH_FACTOR,
    CORRIDOR_CENTER_DECIMALS,
    CORRIDOR_MAX_GROWTH_STEPS,
    CORRIDOR_SIMPLIFY_TOLERANCE_M,
    KM_PER_DEGREE,
    MAX_LATITUDE_DEG,
    METERS_PER_KM,
)
from planning.domain.geometry import (
    longitude_km_per_degree,
    segment_distance_km,
    simplify_indexes,
)
from planning.domain.values import Coordinate

type _Cell = tuple[int, int]
type _SegmentRef = tuple[int, int]


class CorridorCapUnreachable(ValueError):
    """The cell count stayed over the cap after `CORRIDOR_MAX_GROWTH_STEPS` growth steps."""


@dataclass(frozen=True, slots=True)
class Corridor:
    """Cell centers on a lat/lon grid of `cell_size_deg`, sorted by latitude then longitude.

    A center is an integer multiple of the cell size, rounded to `CORRIDOR_CENTER_DECIMALS`.
    """

    cell_size_deg: float
    cells: tuple[Coordinate, ...]


@dataclass(frozen=True, slots=True)
class _Line:
    points: tuple[Coordinate, ...]
    segments: tuple[tuple[int, int], ...]


def _prepare(points: Sequence[Coordinate]) -> _Line:
    kept = simplify_indexes(points, CORRIDOR_SIMPLIFY_TOLERANCE_M)
    segments = tuple(itertools.pairwise(kept)) if len(kept) > 1 else ((0, 0),)
    return _Line(points=tuple(points), segments=segments)


def _band_km() -> float:
    return CORRIDOR_SIMPLIFY_TOLERANCE_M / METERS_PER_KM * CORRIDOR_AMBIGUITY_TOLERANCE_FACTOR


def cell_reach_km(center_latitude_deg: float, cell_size_deg: float, buffer_km: float) -> float:
    """How close a route must pass to a cell's center for the cell to be in the corridor:
    the buffer plus the cell's half-diagonal, so every point within the buffer of a route lies
    in a corridor cell."""
    half_lat_km = cell_size_deg / 2 * KM_PER_DEGREE
    half_lon_km = cell_size_deg / 2 * longitude_km_per_degree(center_latitude_deg)
    return buffer_km + math.hypot(half_lat_km, half_lon_km)


def build_corridor(
    lines: Sequence[Sequence[Coordinate]],
    start_cell_size_deg: float,
    max_cells: int,
    *,
    buffer_km: float = CORRIDOR_BUFFER_KM,
) -> Corridor:
    """The grid cells around the lines, at the smallest size whose cell count fits the cap.

    A cell is in the corridor when some line passes within `cell_reach_km` of its center. The
    size starts at `start_cell_size_deg` (the weather provider's grid) and is multiplied by
    `CORRIDOR_CELL_GROWTH_FACTOR` until at most `max_cells` cells remain.

    Raises:
        CorridorCapUnreachable: the cap is still exceeded after the last growth step.
    """
    prepared = [_prepare(line) for line in lines if line]
    cell_size_deg = start_cell_size_deg
    for _ in range(CORRIDOR_MAX_GROWTH_STEPS + 1):
        cells = _corridor_cells(prepared, cell_size_deg, buffer_km)
        if len(cells) <= max_cells:
            return Corridor(cell_size_deg=cell_size_deg, cells=cells)
        cell_size_deg *= CORRIDOR_CELL_GROWTH_FACTOR
    raise CorridorCapUnreachable(max_cells)


def _center(cell: _Cell, cell_size_deg: float) -> Coordinate:
    row, col = cell
    return Coordinate(
        latitude=round(row * cell_size_deg, CORRIDOR_CENTER_DECIMALS),
        longitude=round(col * cell_size_deg, CORRIDOR_CENTER_DECIMALS),
    )


@dataclass(frozen=True, slots=True)
class _Pass:
    lines: Sequence[_Line]
    cell_size_deg: float
    buffer_km: float

    def reach_km(self, center: Coordinate) -> float:
        return cell_reach_km(center.latitude, self.cell_size_deg, self.buffer_km)


def _corridor_cells(
    lines: Sequence[_Line], cell_size_deg: float, buffer_km: float
) -> tuple[Coordinate, ...]:
    grid = _Pass(lines=lines, cell_size_deg=cell_size_deg, buffer_km=buffer_km)
    band_km = _band_km()
    nearest_km: dict[_Cell, float] = {}
    candidates: defaultdict[_Cell, list[_SegmentRef]] = defaultdict(list)
    widest_reach_km = cell_reach_km(0.0, cell_size_deg, buffer_km) + band_km
    for line_number, line in enumerate(lines):
        for segment_number, (first, last) in enumerate(line.segments):
            start = line.points[first]
            end = line.points[last]
            for cell in _cells_around(start, end, cell_size_deg, widest_reach_km):
                center = _center(cell, cell_size_deg)
                distance_km = segment_distance_km(center, start, end)
                if distance_km > grid.reach_km(center) + band_km:
                    continue
                candidates[cell].append((line_number, segment_number))
                nearest_km[cell] = min(distance_km, nearest_km.get(cell, math.inf))
    included = [
        cell
        for cell, distance_km in nearest_km.items()
        if _is_within(grid, cell, distance_km, candidates[cell])
    ]
    return tuple(_center(cell, cell_size_deg) for cell in sorted(included))


def _is_within(
    grid: _Pass, cell: _Cell, simplified_distance_km: float, segments: Sequence[_SegmentRef]
) -> bool:
    center = _center(cell, grid.cell_size_deg)
    reach_km = grid.reach_km(center)
    if simplified_distance_km <= reach_km - _band_km():
        return True
    for line_number, segment_number in segments:
        line = grid.lines[line_number]
        first, last = line.segments[segment_number]
        pairs = itertools.pairwise(range(first, last + 1)) if last > first else ((first, last),)
        for start_index, end_index in pairs:
            distance_km = segment_distance_km(
                center, line.points[start_index], line.points[end_index]
            )
            if distance_km <= reach_km:
                return True
    return False


def _cells_around(
    start: Coordinate, end: Coordinate, cell_size_deg: float, reach_km: float
) -> itertools.product[tuple[int, int]]:
    margin_lat = reach_km / KM_PER_DEGREE
    low_lat = min(start.latitude, end.latitude) - margin_lat
    high_lat = max(start.latitude, end.latitude) + margin_lat
    widest_lat = min(MAX_LATITUDE_DEG, max(abs(low_lat), abs(high_lat)))
    margin_lon = reach_km / longitude_km_per_degree(widest_lat)
    low_lon = min(start.longitude, end.longitude) - margin_lon
    high_lon = max(start.longitude, end.longitude) + margin_lon
    rows = range(math.ceil(low_lat / cell_size_deg), math.floor(high_lat / cell_size_deg) + 1)
    cols = range(math.ceil(low_lon / cell_size_deg), math.floor(high_lon / cell_size_deg) + 1)
    return itertools.product(rows, cols)
