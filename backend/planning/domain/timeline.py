"""Truck driving times and the driving-and-rest clock (`docs/trip-planning.md`, "Truck speed and
arrival times" and "Rest stops"; ADR 0011).

`build_timeline` turns a provider route into legs (driving or ferry) and stops (break or off
duty), all as elapsed seconds since departure and km along the measured route line.
"""

import itertools
import math
from bisect import bisect_left
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from operator import attrgetter
from types import MappingProxyType

from planning.constants import POINTS_PER_SEGMENT, SECONDS_PER_HOUR, TIMELINE_TOLERANCE_S
from planning.domain.geometry import KmInterval, RouteLine, ferry_intervals_km, km_at_index
from planning.domain.values import ProgressPoint, ProviderRoute
from rulesets.domain.schema import RestRules, RuleSet


class LegKind(StrEnum):
    """What the truck does on a leg."""

    DRIVING = "driving"
    FERRY = "ferry"


class StopKind(StrEnum):
    """A rest stop the clock inserts."""

    BREAK = "break"
    OFF_DUTY = "off_duty"


@dataclass(frozen=True, slots=True)
class StopRule:
    """How long a stop lasts under the rest rules, and whether it starts a new shift."""

    duration_s: Callable[[RestRules], float]
    starts_new_shift: bool


@dataclass(frozen=True, slots=True)
class LegRule:
    """Whether time on a leg of this kind is driving for the rest clock."""

    counts_as_driving: bool


LEG_RULES = MappingProxyType(
    {
        LegKind.DRIVING: LegRule(counts_as_driving=True),
        LegKind.FERRY: LegRule(counts_as_driving=False),
    }
)

STOP_RULES = MappingProxyType(
    {
        StopKind.BREAK: StopRule(duration_s=attrgetter("break_s"), starts_new_shift=False),
        StopKind.OFF_DUTY: StopRule(duration_s=attrgetter("off_duty_s"), starts_new_shift=True),
    }
)


@dataclass(frozen=True, slots=True)
class Leg:
    """A moving part of the trip between two km positions and two elapsed times."""

    kind: LegKind
    start_km: float
    end_km: float
    start_elapsed_s: float
    end_elapsed_s: float

    @property
    def duration_s(self) -> float:
        """Seconds the leg takes."""
        return self.end_elapsed_s - self.start_elapsed_s


@dataclass(frozen=True, slots=True)
class Stop:
    """A rest stop at a km position, starting at an elapsed time."""

    kind: StopKind
    distance_km: float
    start_elapsed_s: float
    duration_s: float

    @property
    def end_elapsed_s(self) -> float:
        """Elapsed seconds when the truck moves on."""
        return self.start_elapsed_s + self.duration_s


@dataclass(frozen=True, slots=True)
class Timeline:
    """Elapsed time along a route: legs in order, the stops between them, and totals.

    `elapsed_s` = `driving_s` + `ferry_s` + `rest_s`; `ferry_s` is all time on legs that do
    not count as driving.
    """

    legs: tuple[Leg, ...]
    stops: tuple[Stop, ...]
    elapsed_s: float
    driving_s: float
    ferry_s: float
    rest_s: float

    def elapsed_at(self, distance_km: float) -> float:
        """Seconds after departure when the truck arrives at `distance_km`.

        Linear within a leg; at a stop's position it is the time the truck arrives there.
        Positions outside the route are clamped to its ends.
        """
        index = bisect_left(self.legs, distance_km, key=attrgetter("end_km"))
        if index == len(self.legs):
            return self.elapsed_s
        leg = self.legs[index]
        length_km = leg.end_km - leg.start_km
        if length_km <= 0:
            return leg.start_elapsed_s
        share = max(0.0, min(1.0, (distance_km - leg.start_km) / length_km))
        return leg.start_elapsed_s + share * leg.duration_s

    def position_at(self, elapsed_s: float) -> float:
        """The truck's km along the route at `elapsed_s` after departure.

        It holds still during a stop; before departure it is at the origin, after arrival at the
        destination.
        """
        if not self.legs:
            return 0.0
        index = bisect_left(self.legs, elapsed_s, key=attrgetter("end_elapsed_s"))
        if index == len(self.legs):
            return self.legs[-1].end_km
        leg = self.legs[index]
        if elapsed_s <= leg.start_elapsed_s or leg.duration_s <= 0:
            return leg.start_km
        share = (elapsed_s - leg.start_elapsed_s) / leg.duration_s
        return leg.start_km + share * (leg.end_km - leg.start_km)


@dataclass(frozen=True, slots=True)
class _Piece:
    kind: LegKind
    start_km: float
    end_km: float
    duration_s: float


def build_timeline(
    route: ProviderRoute, line: RouteLine, rules: RuleSet, *, include_rest: bool
) -> Timeline:
    """The timeline of a route.

    Args:
        route: the provider route; its `progress` gives provider km and seconds per segment.
            With fewer than two progress entries the route's totals make one segment.
        line: the measured route line (`geometry.measure_line(route.points)`); every km in the
            result is on this line's scale.
        rules: speed factor, speed cap (None = no cap) and rest rules.
        include_rest: the trip option; when False no stop is inserted.

    Driving time per segment is the provider's km at
    `min(provider speed x truck_speed_factor, truck_max_speed_kmh)`. Time on a ferry is the
    provider's, unchanged, and is not driving. With rest, a break follows
    `max_driving_before_break_s` of driving, and off duty follows `max_driving_per_shift_s` of
    driving or `max_shift_s` since the shift began, at the exact point the limit is reached.
    Breaks and ferries count toward the shift window.
    """
    pieces = _pieces(route, line, rules)
    clock = _RestClock(rules.rest_rules, enabled=include_rest)
    for piece in pieces:
        clock.add(piece)
    return clock.timeline()


def _progress(route: ProviderRoute, line: RouteLine) -> Sequence[ProgressPoint]:
    if len(route.progress) >= POINTS_PER_SEGMENT:
        return route.progress
    return (
        ProgressPoint(point_index=0, distance_km=0.0, elapsed_s=0.0),
        ProgressPoint(
            point_index=len(line.points) - 1,
            distance_km=route.distance_km,
            elapsed_s=route.travel_time_s,
        ),
    )


def _truck_speed_kmh(provider_km: float, provider_s: float, rules: RuleSet) -> float:
    provider_speed_kmh = provider_km / provider_s * SECONDS_PER_HOUR if provider_s > 0 else math.inf
    truck_speed_kmh = provider_speed_kmh * rules.truck_speed_factor
    if rules.truck_max_speed_kmh is None:
        return truck_speed_kmh
    return min(truck_speed_kmh, rules.truck_max_speed_kmh)


def _pieces(route: ProviderRoute, line: RouteLine, rules: RuleSet) -> list[_Piece]:
    ferries = ferry_intervals_km(line, route.ferry_sections)
    progress = _progress(route, line)
    pieces: list[_Piece] = []
    for start, end in itertools.pairwise(progress):
        start_km = km_at_index(line, start.point_index)
        end_km = max(start_km, km_at_index(line, end.point_index))
        provider_km = max(0.0, end.distance_km - start.distance_km)
        provider_s = max(0.0, end.elapsed_s - start.elapsed_s)
        truck_speed_kmh = _truck_speed_kmh(provider_km, provider_s, rules)
        line_km = end_km - start_km
        for part_start_km, part_end_km in _split_at_ferries(start_km, end_km, ferries):
            share = (part_end_km - part_start_km) / line_km if line_km > 0 else 1.0
            on_ferry = any(ferry.contains((part_start_km + part_end_km) / 2) for ferry in ferries)
            part_provider_km = share * provider_km
            if on_ferry or part_provider_km <= 0:
                duration_s = share * provider_s
            else:
                duration_s = part_provider_km / truck_speed_kmh * SECONDS_PER_HOUR
            kind = LegKind.FERRY if on_ferry else LegKind.DRIVING
            pieces.append(_Piece(kind, part_start_km, part_end_km, duration_s))
    return pieces


def _split_at_ferries(
    start_km: float, end_km: float, ferries: Sequence[KmInterval]
) -> list[tuple[float, float]]:
    cuts = sorted(
        {
            boundary_km
            for ferry in ferries
            for boundary_km in (ferry.start_km, ferry.end_km)
            if start_km < boundary_km < end_km
        }
    )
    bounds = [start_km, *cuts, end_km]
    return list(itertools.pairwise(bounds))


class _RestClock:
    def __init__(self, rest: RestRules, *, enabled: bool) -> None:
        self._rest = rest
        self._enabled = enabled
        self._legs: list[Leg] = []
        self._stops: list[Stop] = []
        self._elapsed_s = 0.0
        self._driving_s = 0.0
        self._ferry_s = 0.0
        self._rest_s = 0.0
        self._since_break_s = 0.0
        self._shift_driving_s = 0.0
        self._shift_elapsed_s = 0.0

    def add(self, piece: _Piece) -> None:
        if LEG_RULES[piece.kind].counts_as_driving:
            self._drive(piece)
            return
        self._leg(piece.kind, piece.start_km, piece.end_km, piece.duration_s)
        self._ferry_s += piece.duration_s
        self._shift_elapsed_s += piece.duration_s

    def timeline(self) -> Timeline:
        return Timeline(
            legs=tuple(self._legs),
            stops=tuple(self._stops),
            elapsed_s=self._elapsed_s,
            driving_s=self._driving_s,
            ferry_s=self._ferry_s,
            rest_s=self._rest_s,
        )

    def _drive(self, piece: _Piece) -> None:
        remaining_s = piece.duration_s
        position_km = piece.start_km
        km_per_s = (piece.end_km - piece.start_km) / remaining_s if remaining_s > 0 else 0.0
        while remaining_s > TIMELINE_TOLERANCE_S:
            due = self._due_stop()
            if due is not None:
                self._stop(due, position_km)
                continue
            step_s = self._time_to_limit_s()
            if step_s >= remaining_s - TIMELINE_TOLERANCE_S:
                step_s = remaining_s
                next_km = piece.end_km
            else:
                next_km = position_km + step_s * km_per_s
            self._leg(LegKind.DRIVING, position_km, next_km, step_s)
            self._count_driving(step_s)
            remaining_s -= step_s
            position_km = next_km
        if position_km < piece.end_km or remaining_s > 0:
            self._leg(LegKind.DRIVING, position_km, piece.end_km, remaining_s)
            self._count_driving(remaining_s)

    def _count_driving(self, duration_s: float) -> None:
        self._driving_s += duration_s
        self._since_break_s += duration_s
        self._shift_driving_s += duration_s
        self._shift_elapsed_s += duration_s

    def _time_to_limit_s(self) -> float:
        if not self._enabled:
            return math.inf
        return min(
            self._rest.max_driving_before_break_s - self._since_break_s,
            self._rest.max_driving_per_shift_s - self._shift_driving_s,
            self._rest.max_shift_s - self._shift_elapsed_s,
        )

    def _due_stop(self) -> StopKind | None:
        if not self._enabled:
            return None
        shift_over = (
            self._shift_driving_s >= self._rest.max_driving_per_shift_s - TIMELINE_TOLERANCE_S
            or self._shift_elapsed_s >= self._rest.max_shift_s - TIMELINE_TOLERANCE_S
        )
        if shift_over:
            return StopKind.OFF_DUTY
        if self._since_break_s >= self._rest.max_driving_before_break_s - TIMELINE_TOLERANCE_S:
            return StopKind.BREAK
        return None

    def _stop(self, kind: StopKind, position_km: float) -> None:
        rule = STOP_RULES[kind]
        duration_s = rule.duration_s(self._rest)
        self._stops.append(Stop(kind, position_km, self._elapsed_s, duration_s))
        self._elapsed_s += duration_s
        self._rest_s += duration_s
        self._since_break_s = 0.0
        if rule.starts_new_shift:
            self._shift_driving_s = 0.0
            self._shift_elapsed_s = 0.0
        else:
            self._shift_elapsed_s += duration_s

    def _leg(self, kind: LegKind, start_km: float, end_km: float, duration_s: float) -> None:
        start_s = self._elapsed_s
        self._elapsed_s += duration_s
        self._legs.append(Leg(kind, start_km, end_km, start_s, self._elapsed_s))
