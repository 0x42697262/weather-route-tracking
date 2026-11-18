"""Whether a candidate route is distinct enough from the kept routes to keep
(`docs/trip-planning.md`, "Reaching 3 routes")."""

import itertools
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from planning.constants import (
    KM_PER_DEGREE,
    MAX_LATITUDE_DEG,
    ROUTE_MAX_OVERLAP_SHARE,
    ROUTE_MAX_TIME_RATIO,
    ROUTE_OVERLAP_INDEX_CELL_DEG,
    ROUTE_OVERLAP_MAX_SAMPLES,
    ROUTE_OVERLAP_SAMPLE_STEP_KM,
    ROUTE_OVERLAP_TOLERANCE_KM,
    SAMPLE_CENTER_SHARE,
)
from planning.domain.geometry import (
    longitude_km_per_degree,
    measure_line,
    point_at_km,
    segment_distance_km,
)
from planning.domain.values import Coordinate

type _Cell = tuple[int, int]
type _Segment = tuple[Coordinate, Coordinate]


class RejectReason(StrEnum):
    """Why a candidate route was not kept. The overlap check comes first."""

    OVERLAPS_KEPT_ROUTE = "overlaps_kept_route"
    TOO_SLOW = "too_slow"


@dataclass(frozen=True, slots=True)
class DistinctDecision:
    """The verdict on a candidate and the two measures it was decided on.

    `reason` is None exactly when `keep` is True. `overlap_share` is in [0, 1]; `time_ratio`
    is the candidate's travel time over the fastest route's.
    """

    keep: bool
    reason: RejectReason | None
    overlap_share: float
    time_ratio: float


class KeptRoutes:
    """The lines of the routes kept so far, indexed for fast "is this point on a kept line"
    tests: segments in a lat/lon grid, each registered in every cell its tolerance-widened
    bounding box touches. Build it once per trip and `add` each kept line."""

    def __init__(self, tolerance_km: float = ROUTE_OVERLAP_TOLERANCE_KM) -> None:
        """An empty index; `tolerance_km` is how close counts as running along a kept line."""
        self._tolerance_km = tolerance_km
        self._segments: list[_Segment] = []
        self._cells: defaultdict[_Cell, list[int]] = defaultdict(list)
        self._line_count = 0

    def __len__(self) -> int:
        """How many lines were added."""
        return self._line_count

    def add(self, line: Sequence[Coordinate]) -> None:
        """Index a kept route's line."""
        self._line_count += 1
        for start, end in itertools.pairwise(line):
            self._add_split(start, end)

    def _add_split(self, start: Coordinate, end: Coordinate) -> None:
        extent_deg = max(abs(end.latitude - start.latitude), abs(end.longitude - start.longitude))
        parts = math.ceil(extent_deg / ROUTE_OVERLAP_INDEX_CELL_DEG)
        if parts <= 1:
            self._add(start, end)
            return
        previous = start
        for part in range(1, parts + 1):
            share = part / parts
            current = Coordinate(
                latitude=start.latitude + (end.latitude - start.latitude) * share,
                longitude=start.longitude + (end.longitude - start.longitude) * share,
            )
            self._add(previous, current)
            previous = current

    def _add(self, start: Coordinate, end: Coordinate) -> None:
        segment_number = len(self._segments)
        self._segments.append((start, end))
        widest_lat = min(MAX_LATITUDE_DEG, max(abs(start.latitude), abs(end.latitude)))
        margin_lat = self._tolerance_km / KM_PER_DEGREE
        margin_lon = self._tolerance_km / longitude_km_per_degree(widest_lat)
        first_row = _cell_number(min(start.latitude, end.latitude) - margin_lat)
        last_row = _cell_number(max(start.latitude, end.latitude) + margin_lat)
        first_col = _cell_number(min(start.longitude, end.longitude) - margin_lon)
        last_col = _cell_number(max(start.longitude, end.longitude) + margin_lon)
        for row in range(first_row, last_row + 1):
            for col in range(first_col, last_col + 1):
                self._cells[row, col].append(segment_number)

    def is_near(self, point: Coordinate) -> bool:
        """Whether a kept segment lies within the tolerance of the point."""
        cell = (_cell_number(point.latitude), _cell_number(point.longitude))
        for segment_number in self._cells.get(cell, ()):
            start, end = self._segments[segment_number]
            if segment_distance_km(point, start, end) <= self._tolerance_km:
                return True
        return False


def _cell_number(value_deg: float) -> int:
    return math.floor(value_deg / ROUTE_OVERLAP_INDEX_CELL_DEG)


def overlap_share(candidate: Sequence[Coordinate], kept: KeptRoutes) -> float:
    """The share of the candidate's length that runs within the tolerance of a kept line.

    The candidate is sampled at equal steps of about `ROUTE_OVERLAP_SAMPLE_STEP_KM` (at most
    `ROUTE_OVERLAP_MAX_SAMPLES` samples), each sample standing for the same length. A candidate
    with no length, or no kept line, gives 0.
    """
    line = measure_line(candidate)
    if line.length_km <= 0 or not kept:
        return 0.0
    sample_count = min(
        ROUTE_OVERLAP_MAX_SAMPLES, max(1, math.ceil(line.length_km / ROUTE_OVERLAP_SAMPLE_STEP_KM))
    )
    step_km = line.length_km / sample_count
    near_count = sum(
        kept.is_near(point_at_km(line, (number + SAMPLE_CENTER_SHARE) * step_km))
        for number in range(sample_count)
    )
    return near_count / sample_count


def time_ratio(candidate_travel_time_s: float, fastest_travel_time_s: float) -> float:
    """Candidate time over fastest time; infinite when the fastest takes no time and the
    candidate does, 1 when neither does."""
    if fastest_travel_time_s > 0:
        return candidate_travel_time_s / fastest_travel_time_s
    return math.inf if candidate_travel_time_s > 0 else 1.0


def is_distinct(
    candidate: Sequence[Coordinate],
    candidate_travel_time_s: float,
    kept: KeptRoutes,
    fastest_travel_time_s: float,
) -> DistinctDecision:
    """Keep a candidate when its overlap share with the kept lines is under
    `ROUTE_MAX_OVERLAP_SHARE` and its time is at most `ROUTE_MAX_TIME_RATIO` times the fastest.
    """
    share = overlap_share(candidate, kept)
    ratio = time_ratio(candidate_travel_time_s, fastest_travel_time_s)
    reason: RejectReason | None = None
    if share >= ROUTE_MAX_OVERLAP_SHARE:
        reason = RejectReason.OVERLAPS_KEPT_ROUTE
    elif ratio > ROUTE_MAX_TIME_RATIO:
        reason = RejectReason.TOO_SLOW
    return DistinctDecision(
        keep=reason is None, reason=reason, overlap_share=share, time_ratio=ratio
    )
