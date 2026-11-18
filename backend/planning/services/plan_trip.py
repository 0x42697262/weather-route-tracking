"""Plan a trip: local checks, routes, checkpoints and arrival times, one weather lookup, risk,
stretches, ranking (`docs/trip-planning.md`, "Planning a trip"). Nothing is stored."""

import logging
import time
from bisect import bisect_left, bisect_right
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType

from planning import text
from planning.constants import KM_PER_DEGREE, SECONDS_PER_HOUR
from planning.domain.checkpoints import checkpoint_count, place_checkpoints, place_samples
from planning.domain.geometry import (
    RouteLine,
    encode_polyline,
    ferry_intervals_km,
    haversine_km,
    point_at_km,
    simplify_indexes,
)
from planning.domain.options import (
    TripOptionName,
    TripOptionsInput,
    build_options,
    resolve_options,
)
from planning.domain.providers import RouteProvider, WeatherProvider
from planning.domain.ranking import Ranking, RankingInput, rank
from planning.domain.refine import added_samples, merge_samples, midpoints_to_sample
from planning.domain.risk import Classification, classify, rule_set_variables
from planning.domain.risk_constants import FORECAST_WINDOW_HOURS, REFINE_MAX_DEPTH
from planning.domain.stretches import RouteSample, Stretch, build_stretches, is_on_ferry
from planning.domain.summary import RouteSummary, summarize
from planning.domain.timeline import Stop, Timeline, build_timeline
from planning.domain.values import (
    CellForecast,
    Coordinate,
    RouteRequest,
    RouteSource,
    TripOptions,
    Vehicle,
)
from planning.domain.weather_lookup import cell_key, values_at
from planning.errors import InvalidRequest, PlanningError, Rejection
from planning.events import (
    CHECKPOINT_CLASSIFIED,
    RECOMMENDATION_NONE,
    REFINE_SAMPLED,
    ROUTE_SUMMARIZED,
    ROUTES_RANKED,
    TRIP_PLANNED,
    TRIP_REJECTED,
    TRIP_REQUESTED,
)
from planning.keys import FIELD_DESTINATION, route_id
from planning.services.checks import check_departure, rejection_reason
from planning.services.constants import (
    FEDERAL_GROSS_LIMIT_KG,
    ROUTES_TARGET,
    SAME_PLACE_MAX_DISTANCE_KM,
)
from planning.services.limits import PlanningLimits
from planning.services.route_options import KeptRoute, RouteBounds, RouteSearch, find_routes
from rulesets.domain.schema import RuleSet, StretchMethod, VersionedRuleSet
from shared.risk_levels import RiskLevel
from shared.weather_variables import WeatherVariable

logger = logging.getLogger(__name__)

MILLISECONDS_PER_SECOND = 1000
ALL_UNKNOWN_SHARE = 1


class TripWarning(StrEnum):
    """Warnings about the whole trip, shown above the route cards."""

    GROSS_WEIGHT_OVER_LIMIT = "gross_weight_over_limit"
    FEWER_ROUTES_THAN_TARGET = "fewer_routes_than_target"
    WEATHER_PARTIAL = "weather_partial"
    WEATHER_UNAVAILABLE = "weather_unavailable"


@dataclass(frozen=True, slots=True)
class StretchSampling:
    """How a stretch method uses samples: whether it adds samples where levels change."""

    refines: bool


STRETCH_SAMPLING: Mapping[StretchMethod, StretchSampling] = MappingProxyType(
    {
        StretchMethod.WORSE_END: StretchSampling(refines=False),
        StretchMethod.REFINE: StretchSampling(refines=True),
    },
)


@dataclass(frozen=True, slots=True)
class TripEnd:
    """An origin or destination: the label the driver picked and its position."""

    label: str
    coordinate: Coordinate


@dataclass(frozen=True, slots=True)
class TripRequest:
    """A trip request, metric and UTC."""

    origin: TripEnd
    destination: TripEnd
    departure_utc: datetime
    options: TripOptionsInput


@dataclass(frozen=True, slots=True)
class PlannedCheckpoint:
    """A checkpoint with its arrival time and weather.

    `level` is what the driver sees: None when Unknown or on a ferry (`on_ferry`), where the
    forecast is shown for information only.
    """

    index: int
    distance_km: float
    coordinate: Coordinate
    arrival_utc: datetime
    values: Mapping[WeatherVariable, float | None]
    classification: Classification
    level: RiskLevel | None
    on_ferry: bool


@dataclass(frozen=True, slots=True)
class PlannedStretch:
    """A stretch and its part of the simplified line, encoded."""

    stretch: Stretch
    polyline: str


@dataclass(frozen=True, slots=True)
class PlannedStop:
    """A rest stop with its position and UTC start."""

    stop: Stop
    coordinate: Coordinate
    start_utc: datetime


@dataclass(frozen=True, slots=True)
class TruckPosition:
    """Where the truck is a whole number of hours after departure."""

    hour: int
    distance_km: float
    coordinate: Coordinate


@dataclass(frozen=True, slots=True)
class PlannedRoute:
    """One route with everything the client draws and lists."""

    route_id: str
    source: RouteSource
    distance_km: float
    polyline: str
    checkpoints: tuple[PlannedCheckpoint, ...]
    stretches: tuple[PlannedStretch, ...]
    stops: tuple[PlannedStop, ...]
    positions_by_hour: tuple[TruckPosition, ...]
    summary: RouteSummary
    timeline: Timeline
    arrival_utc: datetime
    refined_samples: int
    unknown_checkpoints: int


@dataclass(frozen=True, slots=True)
class WeatherReport:
    """How the weather lookup went for the whole trip."""

    cell_size_deg: float
    cells_requested: int
    cells_missing: int
    unknown_checkpoints: int
    refined_samples: int


@dataclass(frozen=True, slots=True)
class TripPlan:
    """The planned trip; `routes` are in ranking order."""

    rule_set_version: int
    stretch_method: StretchMethod
    options_used: TripOptions
    departure_utc: datetime
    vehicle_weight_kg: float
    routes: tuple[PlannedRoute, ...]
    ranking: Ranking
    routes_requested: int
    routes_found: int
    rounds_tried: tuple[RouteSource, ...]
    warnings: tuple[TripWarning, ...]
    weather: WeatherReport


@dataclass(slots=True)
class _Weather:
    provider: WeatherProvider
    variables: tuple[WeatherVariable, ...]
    now_utc: datetime
    max_cells: int
    forecasts: dict[Coordinate, CellForecast] = field(default_factory=dict)
    requested: set[Coordinate] = field(default_factory=set)

    @property
    def cell_size_deg(self) -> float:
        return self.provider.cell_size_deg

    def cell(self, coordinate: Coordinate) -> Coordinate:
        return cell_key(coordinate, self.cell_size_deg)

    def new_cells(self, coordinates: Sequence[Coordinate]) -> list[Coordinate]:
        cells = dict.fromkeys(self.cell(coordinate) for coordinate in coordinates)
        return [cell for cell in cells if cell not in self.requested]

    @property
    def budget(self) -> int:
        return self.max_cells - len(self.requested)

    async def fetch(self, cells: Sequence[Coordinate]) -> None:
        if not cells:
            return
        self.requested.update(cells)
        answered = await self.provider.forecasts(cells, frozenset(self.variables), self.now_utc)
        self.forecasts.update(answered)

    def classify(
        self, coordinate: Coordinate, arrival_utc: datetime, load_kg: float, rules: RuleSet
    ) -> tuple[Mapping[WeatherVariable, float | None], Classification]:
        forecast = self.forecasts.get(self.cell(coordinate))
        values = (
            values_at(forecast, arrival_utc, self.variables)
            if forecast is not None
            else dict.fromkeys(self.variables)
        )
        return values, classify(values, load_kg, rules)


@dataclass(slots=True)
class _RouteWork:
    kept: KeptRoute
    number: int
    timeline: Timeline
    ferries_km: tuple[tuple[float, float], ...]
    checkpoints: list[PlannedCheckpoint] = field(default_factory=list)
    samples: tuple[RouteSample, ...] = ()
    refined_samples: int = 0

    def arrival(self, departure_utc: datetime, distance_km: float) -> datetime:
        return departure_utc + timedelta(seconds=self.timeline.elapsed_at(distance_km))


def _check_local(
    request: TripRequest,
    rules: VersionedRuleSet,
    limits: PlanningLimits,
    now_utc: datetime,
    horizon_hours: int,
) -> TripOptions:
    options = resolve_options(build_options(rules.rules), request.options)
    check_departure(request.departure_utc, now_utc, horizon_hours)
    straight_km = haversine_km(request.origin.coordinate, request.destination.coordinate)
    if straight_km <= SAME_PLACE_MAX_DISTANCE_KM:
        raise InvalidRequest(Rejection.SAME_PLACE, FIELD_DESTINATION, text.SAME_PLACE)
    if straight_km > limits.trip_max_distance_km:
        raise InvalidRequest(Rejection.TRIP_TOO_LONG, FIELD_DESTINATION, text.TRIP_TOO_LONG)
    count = checkpoint_count(straight_km, options.checkpoint_spacing_km)
    if count > limits.max_checkpoints_per_route:
        raise InvalidRequest(
            Rejection.TOO_MANY_CHECKPOINTS,
            TripOptionName.CHECKPOINT_SPACING,
            text.too_many_checkpoints(count, limits.max_checkpoints_per_route),
        )
    if count > limits.weather_max_cells:
        raise _too_many_cells()
    return options


def _too_many_cells() -> InvalidRequest:
    return InvalidRequest(
        Rejection.TOO_MANY_WEATHER_CELLS,
        TripOptionName.CHECKPOINT_SPACING,
        text.TOO_MANY_WEATHER_CELLS,
    )


def _route_work(search: RouteSearch, rules: RuleSet, options: TripOptions) -> list[_RouteWork]:
    works: list[_RouteWork] = []
    for number, kept in enumerate(search.routes, start=1):
        timeline = build_timeline(
            kept.route, kept.line, rules, include_rest=options.include_rest_stops
        )
        ferries = tuple(
            (interval.start_km, interval.end_km)
            for interval in ferry_intervals_km(kept.line, kept.route.ferry_sections)
        )
        works.append(_RouteWork(kept=kept, number=number, timeline=timeline, ferries_km=ferries))
    return works


@dataclass(frozen=True, slots=True)
class _Context:
    request: TripRequest
    options: TripOptions
    rules: RuleSet


async def _classify_checkpoints(
    works: Sequence[_RouteWork], weather: _Weather, context: _Context, max_checkpoints: int
) -> None:
    request, options, rules = context.request, context.options, context.rules
    placed = {
        work.number: place_checkpoints(
            work.kept.line, options.checkpoint_spacing_km, max_checkpoints
        )
        for work in works
    }
    cells = weather.new_cells([point.coordinate for points in placed.values() for point in points])
    if len(cells) > weather.budget:
        raise _too_many_cells()
    await weather.fetch(cells)
    for work in works:
        samples: list[RouteSample] = []
        for checkpoint in placed[work.number]:
            arrival_utc = work.arrival(request.departure_utc, checkpoint.distance_km)
            values, result = weather.classify(
                checkpoint.coordinate, arrival_utc, options.load_kg, rules
            )
            on_ferry = is_on_ferry(checkpoint.distance_km, work.ferries_km)
            work.checkpoints.append(
                PlannedCheckpoint(
                    index=checkpoint.index,
                    distance_km=checkpoint.distance_km,
                    coordinate=checkpoint.coordinate,
                    arrival_utc=arrival_utc,
                    values=values,
                    classification=result,
                    level=None if on_ferry else result.level,
                    on_ferry=on_ferry,
                )
            )
            samples.append(RouteSample(checkpoint.distance_km, result.level, result.decided_by))
            logger.debug(
                CHECKPOINT_CLASSIFIED,
                extra={
                    "route_id": route_id(work.number),
                    "checkpoint": checkpoint.index,
                    "values": {str(key): value for key, value in values.items()},
                    "load_kg": options.load_kg,
                    "level": result.level,
                    "decided_by": result.decided_by,
                },
            )
        work.samples = tuple(samples)


async def _refine(works: Sequence[_RouteWork], weather: _Weather, context: _Context) -> None:
    request, options, rules = context.request, context.options, context.rules
    min_length_km = weather.cell_size_deg * KM_PER_DEGREE
    for depth in range(1, REFINE_MAX_DEPTH + 1):
        wanted = {
            work.number: place_samples(
                work.kept.line, midpoints_to_sample(work.samples, min_length_km)
            )
            for work in works
        }
        allowed = set(weather.requested)
        allowed.update(
            weather.new_cells(
                [sample.coordinate for samples in wanted.values() for sample in samples]
            )[: max(0, weather.budget)]
        )
        chosen = {
            number: [sample for sample in samples if weather.cell(sample.coordinate) in allowed]
            for number, samples in wanted.items()
        }
        if not any(chosen.values()):
            return
        await weather.fetch(
            weather.new_cells(
                [sample.coordinate for samples in chosen.values() for sample in samples]
            )
        )
        added = 0
        for work in works:
            new_samples = []
            for sample in chosen[work.number]:
                arrival_utc = work.arrival(request.departure_utc, sample.distance_km)
                _, result = weather.classify(sample.coordinate, arrival_utc, options.load_kg, rules)
                new_samples.append(
                    RouteSample(sample.distance_km, result.level, result.decided_by, refined=True)
                )
            kept = added_samples(work.samples, new_samples)
            work.samples = merge_samples(work.samples, new_samples)
            work.refined_samples += len(kept)
            added += len(kept)
        logger.info(REFINE_SAMPLED, extra={"depth": depth, "samples": added})


def _merged_for_display(stretches: Sequence[Stretch]) -> list[Stretch]:
    merged: list[Stretch] = []
    for stretch in stretches:
        previous = merged[-1] if merged else None
        if previous and (previous.level, previous.kind) == (stretch.level, stretch.kind):
            merged[-1] = Stretch(previous.start_km, stretch.end_km, stretch.level, stretch.kind)
        else:
            merged.append(stretch)
    return merged


@dataclass(frozen=True, slots=True)
class _SimplifiedLine:
    line: RouteLine
    indexes: tuple[int, ...]
    kms: tuple[float, ...]

    def between(self, start_km: float, end_km: float) -> list[Coordinate]:
        first = bisect_right(self.kms, start_km)
        last = bisect_left(self.kms, end_km)
        inner = [self.line.points[self.indexes[index]] for index in range(first, last)]
        return [point_at_km(self.line, start_km), *inner, point_at_km(self.line, end_km)]


def _simplified(line: RouteLine) -> _SimplifiedLine:
    indexes = simplify_indexes(line.points)
    return _SimplifiedLine(
        line=line,
        indexes=indexes,
        kms=tuple(line.cumulative_km[index] for index in indexes),
    )


def _positions_by_hour(work: _RouteWork) -> tuple[TruckPosition, ...]:
    positions: list[TruckPosition] = []
    for hour in range(FORECAST_WINDOW_HOURS + 1):
        distance_km = work.timeline.position_at(hour * SECONDS_PER_HOUR)
        positions.append(
            TruckPosition(
                hour=hour,
                distance_km=distance_km,
                coordinate=point_at_km(work.kept.line, distance_km),
            )
        )
    return tuple(positions)


def _planned_route(work: _RouteWork, rules: RuleSet, departure_utc: datetime) -> PlannedRoute:
    line = work.kept.line
    stretches = build_stretches(
        work.samples, rules.stretch_method, work.ferries_km, rules.ferry_level
    )
    summary = summarize(stretches)
    simple = _simplified(line)
    simple_points = [line.points[index] for index in simple.indexes]
    planned_stretches = tuple(
        PlannedStretch(
            stretch=stretch,
            polyline=encode_polyline(simple.between(stretch.start_km, stretch.end_km)),
        )
        for stretch in _merged_for_display(stretches)
    )
    stops = tuple(
        PlannedStop(
            stop=stop,
            coordinate=point_at_km(line, stop.distance_km),
            start_utc=departure_utc + timedelta(seconds=stop.start_elapsed_s),
        )
        for stop in work.timeline.stops
    )
    unknown = sum(1 for point in work.checkpoints if point.classification.level is None)
    planned = PlannedRoute(
        route_id=route_id(work.number),
        source=work.kept.source,
        distance_km=line.length_km,
        polyline=encode_polyline(simple_points),
        checkpoints=tuple(work.checkpoints),
        stretches=planned_stretches,
        stops=stops,
        positions_by_hour=_positions_by_hour(work),
        summary=summary,
        timeline=work.timeline,
        arrival_utc=departure_utc + timedelta(seconds=work.timeline.elapsed_s),
        refined_samples=work.refined_samples,
        unknown_checkpoints=unknown,
    )
    logger.info(
        ROUTE_SUMMARIZED,
        extra={
            "route_id": planned.route_id,
            "source": planned.source,
            "total_km": round(summary.total_km, 3),
            "unknown_km": round(summary.unknown_km, 3),
            "average_risk": summary.average_risk,
            "travel_time_s": round(work.timeline.elapsed_s),
            "warnings": [warning.value for warning in summary.warnings],
        },
    )
    return planned


def _rank(routes: Sequence[PlannedRoute], max_unknown_share: float | None) -> Ranking:
    ranking = rank(
        [RankingInput(route.route_id, route.summary, route.timeline.elapsed_s) for route in routes],
        max_unknown_share,
    )
    logger.info(
        ROUTES_RANKED,
        extra={"keys": {key.route_id: key.values for key in ranking.keys}},
    )
    if ranking.no_recommendation_reason is not None:
        logger.info(RECOMMENDATION_NONE, extra={"reason": ranking.no_recommendation_reason})
    return ranking


WarningRule = Callable[["_TripFacts"], bool]


@dataclass(frozen=True, slots=True)
class _TripFacts:
    vehicle_weight_kg: float
    routes_found: int
    checkpoints: int
    unknown_checkpoints: int


TRIP_WARNING_RULES: Mapping[TripWarning, WarningRule] = MappingProxyType(
    {
        TripWarning.GROSS_WEIGHT_OVER_LIMIT: lambda facts: (
            facts.vehicle_weight_kg > FEDERAL_GROSS_LIMIT_KG
        ),
        TripWarning.FEWER_ROUTES_THAN_TARGET: lambda facts: facts.routes_found < ROUTES_TARGET,
        TripWarning.WEATHER_PARTIAL: lambda facts: (
            0 < facts.unknown_checkpoints < facts.checkpoints
        ),
        TripWarning.WEATHER_UNAVAILABLE: lambda facts: (
            facts.checkpoints > 0 and facts.unknown_checkpoints == facts.checkpoints
        ),
    },
)


def _warnings(facts: _TripFacts) -> tuple[TripWarning, ...]:
    return tuple(warning for warning, applies in TRIP_WARNING_RULES.items() if applies(facts))


async def plan_trip(  # noqa: PLR0913
    request: TripRequest,
    *,
    routes: RouteProvider,
    route_provider_name: str,
    weather: WeatherProvider,
    rule_set: VersionedRuleSet,
    limits: PlanningLimits,
    now_utc: datetime,
) -> TripPlan:
    """Plan a trip in the order of `docs/trip-planning.md`: local checks before any outbound
    call, then routes, checkpoints, one weather lookup, risk, stretches and ranking.

    Raises:
        TripOptionsInvalid, InvalidRequest: a local check failed; no provider was called.
        InvalidRequest: the fastest route is too long or needs too many checkpoints or cells.
        NoRoadRoute, UpstreamUnavailable, UpstreamBusy, UpstreamInvalidResponse: routing failed.
    """
    started_s = time.perf_counter()
    logger.info(
        TRIP_REQUESTED,
        extra={
            "departure_utc": request.departure_utc.isoformat(),
            "rule_set_version": rule_set.version,
        },
    )
    try:
        plan = await _plan(
            request,
            routes=routes,
            route_provider_name=route_provider_name,
            weather=weather,
            rule_set=rule_set,
            limits=limits,
            now_utc=now_utc,
        )
    except PlanningError as error:
        logger.info(TRIP_REJECTED, extra={"reason": rejection_reason(error)})
        raise
    recommended = plan.ranking.recommended_id
    logger.info(
        TRIP_PLANNED,
        extra={
            "route_count": plan.routes_found,
            "recommended_route": recommended,
            "best_available_route": plan.ranking.best_available_id,
            "duration_ms": round((time.perf_counter() - started_s) * MILLISECONDS_PER_SECOND),
        },
    )
    return plan


async def _plan(  # noqa: PLR0913
    request: TripRequest,
    *,
    routes: RouteProvider,
    route_provider_name: str,
    weather: WeatherProvider,
    rule_set: VersionedRuleSet,
    limits: PlanningLimits,
    now_utc: datetime,
) -> TripPlan:
    rules = rule_set.rules
    options = _check_local(request, rule_set, limits, now_utc, weather.forecast_horizon_hours)
    vehicle = Vehicle(
        weight_kg=rules.empty_vehicle_weight_kg + options.load_kg,
        max_speed_kmh=rules.truck_max_speed_kmh,
    )
    search = await find_routes(
        routes,
        route_provider_name,
        RouteRequest(
            origin=request.origin.coordinate,
            destination=request.destination.coordinate,
            departure_utc=request.departure_utc,
            vehicle=vehicle,
            alternatives=limits.route_alternatives_requested,
            avoid=frozenset(),
            via=(),
        ),
        RouteBounds(
            max_distance_km=limits.trip_max_distance_km,
            spacing_km=options.checkpoint_spacing_km,
            max_checkpoints=limits.max_checkpoints_per_route,
        ),
        alternatives_requested=limits.route_alternatives_requested,
        max_extra_requests=limits.route_max_extra_requests,
    )
    works = _route_work(search, rules, options)
    book = _Weather(
        provider=weather,
        variables=rule_set_variables(rules),
        now_utc=now_utc,
        max_cells=limits.weather_max_cells,
    )
    context = _Context(request=request, options=options, rules=rules)
    await _classify_checkpoints(works, book, context, limits.max_checkpoints_per_route)
    if STRETCH_SAMPLING[rules.stretch_method].refines:
        await _refine(works, book, context)
    planned = [_planned_route(work, rules, request.departure_utc) for work in works]
    ranking = _rank(planned, rules.max_unknown_share)
    by_id = {route.route_id: route for route in planned}
    checkpoints = sum(len(route.checkpoints) for route in planned)
    unknown = sum(route.unknown_checkpoints for route in planned)
    facts = _TripFacts(vehicle.weight_kg, len(planned), checkpoints, unknown)
    return TripPlan(
        rule_set_version=rule_set.version,
        stretch_method=rules.stretch_method,
        options_used=options,
        departure_utc=request.departure_utc,
        vehicle_weight_kg=vehicle.weight_kg,
        routes=tuple(by_id[identifier] for identifier in ranking.order),
        ranking=ranking,
        routes_requested=ROUTES_TARGET,
        routes_found=len(planned),
        rounds_tried=search.rounds_tried,
        warnings=_warnings(facts),
        weather=WeatherReport(
            cell_size_deg=weather.cell_size_deg,
            cells_requested=len(book.requested),
            cells_missing=len(book.requested - set(book.forecasts)),
            unknown_checkpoints=unknown,
            refined_samples=sum(route.refined_samples for route in planned),
        ),
    )
