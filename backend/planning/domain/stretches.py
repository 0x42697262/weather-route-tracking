"""Turn classified samples along a route into stretches (`docs/risk-model.md` step 4 and ferry
stretches)."""

import itertools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from rulesets.domain.schema import StretchMethod
from shared.risk_levels import RiskLevel, worse

type KmInterval = tuple[float, float]


@dataclass(frozen=True, slots=True)
class RouteSample:
    """A classified point on a route.

    Attributes:
        distance_km: distance from the origin along the route.
        level: its level from weather, None when Unknown.
        decided_by: what decided the level (`planning.domain.risk.Classification`).
        refined: added by refinement; not shown as a checkpoint.
    """

    distance_km: float
    level: RiskLevel | None
    decided_by: str | None
    refined: bool = False


class StretchKind(StrEnum):
    """Where a stretch's level comes from. Its properties are in
    `planning.domain.summary.STRETCH_KINDS`."""

    RATED = "rated"
    UNKNOWN = "unknown"
    FERRY = "ferry"


@dataclass(frozen=True, slots=True)
class Stretch:
    """A part of a route with one level.

    `level` is None for an Unknown stretch and for a ferry stretch that is not rated.
    """

    start_km: float
    end_km: float
    level: RiskLevel | None
    kind: StretchKind

    @property
    def length_km(self) -> float:
        """The stretch's length."""
        return self.end_km - self.start_km


def _weather_stretch(start_km: float, end_km: float, level: RiskLevel | None) -> Stretch:
    kind = StretchKind.UNKNOWN if level is None else StretchKind.RATED
    return Stretch(start_km=start_km, end_km=end_km, level=level, kind=kind)


def _worse_end_level(first: RouteSample, second: RouteSample) -> RiskLevel | None:
    if first.level is None or second.level is None:
        return None
    return worse(first.level, second.level)


def worse_end(samples: Sequence[RouteSample]) -> tuple[Stretch, ...]:
    """One stretch per pair of neighboring samples, at the worse level of its ends; Unknown when
    either end is Unknown. Pairs at the same distance give no stretch."""
    return tuple(
        _weather_stretch(first.distance_km, second.distance_km, _worse_end_level(first, second))
        for first, second in itertools.pairwise(samples)
        if second.distance_km > first.distance_km
    )


STRETCH_METHODS: Mapping[StretchMethod, Callable[[Sequence[RouteSample]], tuple[Stretch, ...]]] = (
    MappingProxyType(
        {
            StretchMethod.WORSE_END: worse_end,
            StretchMethod.REFINE: worse_end,
        },
    )
)


def merge_intervals(intervals: Sequence[KmInterval]) -> tuple[KmInterval, ...]:
    """The intervals sorted, with overlapping or touching ones joined and empty ones dropped."""
    merged: list[KmInterval] = []
    for start_km, end_km in sorted(intervals):
        if end_km <= start_km:
            continue
        if merged and start_km <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end_km))
        else:
            merged.append((start_km, end_km))
    return tuple(merged)


def is_on_ferry(distance_km: float, ferry_intervals_km: Sequence[KmInterval]) -> bool:
    """The distance lies on a ferry section, ends included. A checkpoint there shows its forecast
    but no level."""
    return any(start_km <= distance_km <= end_km for start_km, end_km in ferry_intervals_km)


def _split_by_ferries(
    stretch: Stretch, ferries: tuple[KmInterval, ...], ferry_level: RiskLevel | None
) -> list[Stretch]:
    pieces: list[Stretch] = []
    cursor_km = stretch.start_km
    for ferry_start_km, ferry_end_km in ferries:
        overlap_start_km = max(cursor_km, ferry_start_km)
        overlap_end_km = min(stretch.end_km, ferry_end_km)
        if overlap_end_km <= overlap_start_km:
            continue
        if overlap_start_km > cursor_km:
            pieces.append(_weather_stretch(cursor_km, overlap_start_km, stretch.level))
        pieces.append(Stretch(overlap_start_km, overlap_end_km, ferry_level, StretchKind.FERRY))
        cursor_km = overlap_end_km
    if stretch.end_km > cursor_km:
        pieces.append(_weather_stretch(cursor_km, stretch.end_km, stretch.level))
    return pieces


def build_stretches(
    samples: Sequence[RouteSample],
    method: StretchMethod,
    ferry_intervals_km: Sequence[KmInterval],
    ferry_level: RiskLevel | None,
) -> tuple[Stretch, ...]:
    """Stretches covering the route from the first to the last sample, in order.

    `samples` are ordered by distance and carry their weather level even on a ferry. The method
    rates stretches from the samples; then each part inside a ferry interval becomes a ferry
    stretch at `ferry_level` (None means not rated), and the rest keeps its rated level.
    """
    ferries = merge_intervals(ferry_intervals_km)
    rated = STRETCH_METHODS[method](samples)
    return tuple(
        piece for stretch in rated for piece in _split_by_ferries(stretch, ferries, ferry_level)
    )
