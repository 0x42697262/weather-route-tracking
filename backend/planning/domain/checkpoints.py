"""Checkpoints along a route line (`docs/trip-planning.md`, "Checkpoints") and samples at
arbitrary km positions."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from planning.constants import CHECKPOINT_MIN_FINAL_GAP_SPACING_SHARE, ENDPOINT_CHECKPOINT_COUNT
from planning.domain.geometry import RouteLine, point_at_km
from planning.domain.values import Coordinate
from planning.errors import ErrorCode, PlanningError


class TooManyCheckpoints(PlanningError):
    """The spacing would put more checkpoints on a route than the cap allows; a wider spacing
    fixes it."""

    code = ErrorCode.INVALID_REQUEST

    def __init__(self, count: int, cap: int) -> None:
        """Keep the count the spacing would need and the cap it exceeds."""
        super().__init__(count, cap)
        self.count = count
        self.cap = cap


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """A checkpoint: its order on the route (0 is the origin), km from the origin, position."""

    index: int
    distance_km: float
    coordinate: Coordinate


@dataclass(frozen=True, slots=True)
class Sample:
    """A position at a km along a route that is not a checkpoint (refinement, truck markers)."""

    distance_km: float
    coordinate: Coordinate


def checkpoint_distances_km(length_km: float, spacing_km: float) -> tuple[float, ...]:
    """0, every multiple of `spacing_km` (> 0) short of the end, and the end.

    The last multiple is dropped when it is closer to the end than
    `CHECKPOINT_MIN_FINAL_GAP_SPACING_SHARE` of the spacing, so the final stretch is no sliver.
    The origin and destination are always present, even on a line with no length.
    """
    multiples = _kept_multiple_count(length_km, spacing_km)
    return (0.0, *(spacing_km * number for number in range(1, multiples + 1)), length_km)


def checkpoint_count(length_km: float, spacing_km: float) -> int:
    """How many checkpoints `checkpoint_distances_km` gives, without building them."""
    return _kept_multiple_count(length_km, spacing_km) + ENDPOINT_CHECKPOINT_COUNT


def _kept_multiple_count(length_km: float, spacing_km: float) -> int:
    if length_km <= 0:
        return 0
    count = max(0, math.ceil(length_km / spacing_km) - 1)
    while count and spacing_km * count >= length_km:
        count -= 1
    while spacing_km * (count + 1) < length_km:
        count += 1
    final_gap_km = length_km - spacing_km * count
    if count and final_gap_km < spacing_km * CHECKPOINT_MIN_FINAL_GAP_SPACING_SHARE:
        count -= 1
    return count


def place_checkpoints(line: RouteLine, spacing_km: float, max_count: int) -> tuple[Checkpoint, ...]:
    """The checkpoints of a route line, positions interpolated on their segments.

    Raises:
        TooManyCheckpoints: there would be more than `max_count`.
    """
    count = checkpoint_count(line.length_km, spacing_km)
    if count > max_count:
        raise TooManyCheckpoints(count, max_count)
    return tuple(
        Checkpoint(index=index, distance_km=distance_km, coordinate=point_at_km(line, distance_km))
        for index, distance_km in enumerate(checkpoint_distances_km(line.length_km, spacing_km))
    )


def place_samples(line: RouteLine, distances_km: Sequence[float]) -> tuple[Sample, ...]:
    """Samples at the given km positions, in the order given, clamped to the line."""
    return tuple(
        Sample(distance_km=distance_km, coordinate=point_at_km(line, distance_km))
        for distance_km in distances_km
    )
