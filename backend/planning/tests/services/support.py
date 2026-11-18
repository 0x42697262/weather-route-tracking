"""Fakes and fixed values for service tests: scripted routing, recording weather, a fixed clock."""

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache.backends.locmem import LocMemCache

from planning.adapters.fake.routes import synthetic_route
from planning.domain.options import TripOptionsInput
from planning.domain.values import (
    Avoidance,
    CellForecast,
    Coordinate,
    ProviderRoute,
    RouteRequest,
)
from planning.services.limits import PlanningLimits
from planning.services.plan_trip import TripEnd, TripRequest
from rulesets.domain.defaults import default_rule_set_document
from rulesets.domain.schema import RuleSet, StretchMethod, VersionedRuleSet
from rulesets.domain.validator import validate_rule_set
from shared.weather_variables import WeatherVariable

NOW = datetime(2026, 11, 18, 12, tzinfo=UTC)
DEPARTURE = NOW + timedelta(hours=2)
DALLAS = Coordinate(32.7767, -96.797)
OKLAHOMA_CITY = Coordinate(35.4676, -97.5164)
CHICAGO = Coordinate(41.8781, -87.6298)
DENVER = Coordinate(39.7392, -104.9903)
LOAD_KG = 15000.0
CELL_SIZE_DEG = 0.1
HORIZON_HOURS = 144
FAST_KMH = 85.0
CALM = {
    WeatherVariable.WIND_SPEED: 10.0,
    WeatherVariable.RAIN_RATE: 0.0,
    WeatherVariable.SNOWFALL_RATE: 0.0,
}
NO_TRAVEL_WIND = {**CALM, WeatherVariable.WIND_SPEED: 120.0}
SEVERE_WIND = {**CALM, WeatherVariable.WIND_SPEED: 80.0}

RULES = validate_rule_set(default_rule_set_document())
RULE_SET = VersionedRuleSet(version=1, rules=RULES)
LIMITS = PlanningLimits(
    trip_max_distance_km=3000.0,
    max_checkpoints_per_route=200,
    route_alternatives_requested=4,
    route_max_extra_requests=4,
    weather_max_cells=300,
)


def rule_set_with(**changes: object) -> VersionedRuleSet:
    """The default rule set with some fields replaced."""
    rules: RuleSet = dataclasses.replace(RULES, **changes)  # type: ignore[arg-type]
    return VersionedRuleSet(version=1, rules=rules)


REFINE_RULE_SET = rule_set_with(stretch_method=StretchMethod.REFINE)


def trip(  # noqa: PLR0913
    origin: Coordinate = DALLAS,
    destination: Coordinate = OKLAHOMA_CITY,
    *,
    departure_utc: datetime = DEPARTURE,
    load_kg: float | None = LOAD_KG,
    spacing_km: float | None = None,
    include_rest_stops: bool | None = None,
) -> TripRequest:
    """A trip request with defaults for every field."""
    return TripRequest(
        origin=TripEnd(label="Origin", coordinate=origin),
        destination=TripEnd(label="Destination", coordinate=destination),
        departure_utc=departure_utc,
        options=TripOptionsInput(
            checkpoint_spacing_km=spacing_km,
            include_rest_stops=include_rest_stops,
            load_kg=load_kg,
        ),
    )


def route(
    origin: Coordinate = DALLAS,
    destination: Coordinate = OKLAHOMA_CITY,
    bow_share: float = 0.0,
    speed_kmh: float = FAST_KMH,
) -> ProviderRoute:
    """A synthetic route; different bows give distinct routes."""
    return synthetic_route((origin, destination), bow_share, speed_kmh)


type Answer = Callable[[RouteRequest], tuple[ProviderRoute, ...]]


@dataclass(slots=True)
class ScriptedRoutes:
    """A `RouteProvider` answering each request in turn from `answers`; records every request."""

    answers: list[Answer | tuple[ProviderRoute, ...] | Exception]
    supported_avoidances: frozenset[Avoidance] = frozenset(Avoidance)
    supports_via: bool = True
    max_alternatives: int = 5
    requests: list[RouteRequest] = field(default_factory=list)

    async def routes(self, request: RouteRequest) -> tuple[ProviderRoute, ...]:
        """The next scripted answer."""
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        if callable(answer):
            return answer(request)
        return answer


type Pattern = Callable[[Coordinate, datetime], Mapping[WeatherVariable, float]]


def calm(_cell: Coordinate, _moment: datetime) -> Mapping[WeatherVariable, float]:
    """Calm everywhere, always."""
    return CALM


@dataclass(slots=True)
class RecordingWeather:
    """A `WeatherProvider` reading values from `pattern`; cells for which `fails` is true are
    left out. Records the cells of every call."""

    pattern: Pattern = calm
    fails: Callable[[Coordinate], bool] = lambda _cell: False
    cell_size_deg: float = CELL_SIZE_DEG
    forecast_horizon_hours: int = HORIZON_HOURS
    calls: list[list[Coordinate]] = field(default_factory=list)

    @property
    def cells_seen(self) -> list[Coordinate]:
        """Every cell asked for, in order."""
        return [cell for call in self.calls for cell in call]

    async def forecasts(
        self,
        cells: Sequence[Coordinate],
        variables: frozenset[WeatherVariable],
        now_utc: datetime,
    ) -> Mapping[Coordinate, CellForecast]:
        """Hourly values from 00:00 UTC of `now_utc`'s day for the horizon plus a day."""
        self.calls.append(list(cells))
        start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        hours = tuple(
            start + timedelta(hours=number) for number in range(self.forecast_horizon_hours + 24)
        )
        return {
            cell: CellForecast(
                cell=cell,
                hours_utc=hours,
                values={
                    variable: tuple(self.pattern(cell, moment)[variable] for moment in hours)
                    for variable in variables
                },
            )
            for cell in cells
            if not self.fails(cell)
        }


def north_of(latitude: float, values: Mapping[WeatherVariable, float]) -> Pattern:
    """`values` north of a latitude, calm elsewhere."""

    def pattern(cell: Coordinate, _moment: datetime) -> Mapping[WeatherVariable, float]:
        return values if cell.latitude > latitude else CALM

    return pattern


class RecordingCache(LocMemCache):
    """An in-process cache that records the key of every write."""

    def __init__(self, name: str) -> None:
        """A fresh, empty cache."""
        super().__init__(name, {})
        self.written: list[str] = []

    def set(
        self,
        key: str,
        value: object,
        timeout: float | None = DEFAULT_TIMEOUT,
        version: int | None = None,
    ) -> None:
        """Record the key, then store."""
        self.written.append(key)
        super().set(key, value, timeout, version)

    def add(
        self,
        key: str,
        value: object,
        timeout: float | None = DEFAULT_TIMEOUT,
        version: int | None = None,
    ) -> bool:
        """Record the key, then store if absent."""
        self.written.append(key)
        return super().add(key, value, timeout, version)
