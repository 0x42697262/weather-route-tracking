"""Request and response schemas of `POST /api/v1/trips` (the contract), and their conversion.

Every value is metric and every time is UTC; the client converts for display.
"""

from datetime import datetime
from typing import Annotated

from ninja import Schema
from pydantic import AwareDatetime, ConfigDict, Field

from planning.api.inputs import DistanceIn, Latitude, Longitude, MassIn, to_utc
from planning.domain.options import TripOptionsInput
from planning.domain.ranking import (
    RANKING_KEY_NAMES,
    NoRecommendationReason,
    NotRecommendableReason,
    Ranking,
)
from planning.domain.risk import ConditionLevel
from planning.domain.stretches import StretchKind
from planning.domain.summary import RouteWarning
from planning.domain.timeline import StopKind
from planning.domain.values import Coordinate, RouteSource
from planning.services.constants import (
    OUTPUT_COORDINATE_DECIMALS,
    OUTPUT_DISTANCE_DECIMALS,
    OUTPUT_DURATION_DECIMALS,
    PLACE_LABEL_MAX_CHARS,
)
from planning.services.plan_trip import (
    PlannedCheckpoint,
    PlannedRoute,
    TripEnd,
    TripPlan,
    TripRequest,
    TripWarning,
)
from rulesets.domain.schema import StretchMethod
from shared.risk_levels import RiskLevel
from shared.weather_variables import WeatherVariable


class TripEndIn(Schema):
    """A place the driver picked: its label and position."""

    model_config = ConfigDict(extra="forbid")

    label: Annotated[str, Field(min_length=1, max_length=PLACE_LABEL_MAX_CHARS)]
    latitude: Latitude
    longitude: Longitude


class TripIn(Schema):
    """A trip to plan. Omitted options take their defaults from `GET /api/v1/options`."""

    model_config = ConfigDict(extra="forbid")

    origin: TripEndIn
    destination: TripEndIn
    departure_utc: AwareDatetime
    load_weight: MassIn
    checkpoint_spacing: DistanceIn | None = None
    include_rest_stops: bool | None = None


def _end(place: TripEndIn) -> TripEnd:
    return TripEnd(
        label=place.label,
        coordinate=Coordinate(latitude=place.latitude, longitude=place.longitude),
    )


def trip_request(payload: TripIn) -> TripRequest:
    """The service request: metric quantities and a UTC departure."""
    spacing = payload.checkpoint_spacing
    return TripRequest(
        origin=_end(payload.origin),
        destination=_end(payload.destination),
        departure_utc=to_utc(payload.departure_utc),
        options=TripOptionsInput(
            checkpoint_spacing_km=spacing.metric() if spacing is not None else None,
            include_rest_stops=payload.include_rest_stops,
            load_kg=payload.load_weight.metric(),
        ),
    )


class ConditionOut(Schema):
    """One condition at a checkpoint: its value and level (band level raised by load rules)."""

    variable: WeatherVariable
    value: float | None
    band_level: RiskLevel | None
    level: RiskLevel | None


class CheckpointOut(Schema):
    """A checkpoint. `level` is null when Unknown or on a ferry; `weather_level` is the level
    from the forecast even on a ferry."""

    index: int
    distance_km: float
    latitude: float
    longitude: float
    arrival_utc: datetime
    values: dict[WeatherVariable, float | None]
    level: RiskLevel | None
    weather_level: RiskLevel | None
    decided_by: str | None
    conditions: list[ConditionOut]
    on_ferry: bool


class StretchOut(Schema):
    """A part of the route with one level; `polyline` is its line (Google encoded, precision 5).
    `level` is null for Unknown and for a ferry that is not rated."""

    start_km: float
    end_km: float
    level: RiskLevel | None
    kind: StretchKind
    polyline: str


class StopOut(Schema):
    """A rest stop the clock inserted."""

    kind: StopKind
    distance_km: float
    latitude: float
    longitude: float
    start_utc: datetime
    duration_s: float


class TruckPositionOut(Schema):
    """Where the truck is `hour` whole hours after departure; it stays at the destination after
    arrival."""

    hour: int
    distance_km: float
    latitude: float
    longitude: float


class RouteSummaryOut(Schema):
    """Distances, risk and time of one route."""

    distance_km_by_level: dict[RiskLevel, float]
    unknown_km: float
    ferry_km: float
    total_km: float
    worst_level: RiskLevel | None
    blocking_km: float
    average_risk: float | None
    blocked: bool
    driving_s: float
    rest_s: float
    ferry_s: float
    travel_time_s: float
    arrival_utc: datetime
    warnings: list[RouteWarning]


class RouteOut(Schema):
    """One route, in ranking order; `rank` 1 is the best. `source` says how it was found and
    is also its label's text key."""

    id: str
    rank: int
    recommended: bool
    best_available: bool
    not_recommendable_reason: NotRecommendableReason | None
    source: RouteSource
    distance_km: float
    polyline: str
    summary: RouteSummaryOut
    checkpoints: list[CheckpointOut]
    stretches: list[StretchOut]
    stops: list[StopOut]
    positions_by_hour: list[TruckPositionOut]
    refined_samples: int


class RankingKeyOut(Schema):
    """A route's rounded ranking key, one value per entry of `key_names`."""

    route_id: str
    values: list[float | None]
    has_known_weather: bool


class RankingOut(Schema):
    """The ranking keys, smallest first."""

    key_names: list[str]
    keys: list[RankingKeyOut]


class OptionsUsedOut(Schema):
    """The effective trip options, metric."""

    checkpoint_spacing_km: float
    include_rest_stops: bool
    load_kg: float


class WeatherReportOut(Schema):
    """How the weather lookup went."""

    cell_size_deg: float
    cells_requested: int
    cells_missing: int
    unknown_checkpoints: int
    refined_samples: int


class TripOut(Schema):
    """A planned trip. Exactly one of `recommended_route_id` and `no_recommendation_reason` is
    set. Without a recommendation, `best_available_route_id` names the top-ranked route."""

    rule_set_version: int
    stretch_method: StretchMethod
    departure_utc: datetime
    vehicle_weight_kg: float
    options_used: OptionsUsedOut
    routes: list[RouteOut]
    ranking: RankingOut
    recommended_route_id: str | None
    no_recommendation_reason: NoRecommendationReason | None
    best_available_route_id: str | None
    routes_requested: int
    routes_found: int
    fewer_routes_than_requested: bool
    rounds_tried: list[RouteSource]
    warnings: list[TripWarning]
    weather: WeatherReportOut


def _km(value: float) -> float:
    return round(value, OUTPUT_DISTANCE_DECIMALS)


def _degrees(value: float) -> float:
    return round(value, OUTPUT_COORDINATE_DECIMALS)


def _seconds(value: float) -> float:
    return round(value, OUTPUT_DURATION_DECIMALS)


def _condition_out(condition: ConditionLevel) -> ConditionOut:
    return ConditionOut(
        variable=condition.variable,
        value=condition.value,
        band_level=condition.band_level,
        level=condition.level,
    )


def _checkpoint_out(checkpoint: PlannedCheckpoint) -> CheckpointOut:
    result = checkpoint.classification
    return CheckpointOut(
        index=checkpoint.index,
        distance_km=_km(checkpoint.distance_km),
        latitude=_degrees(checkpoint.coordinate.latitude),
        longitude=_degrees(checkpoint.coordinate.longitude),
        arrival_utc=checkpoint.arrival_utc,
        values=dict(checkpoint.values),
        level=checkpoint.level,
        weather_level=result.level,
        decided_by=result.decided_by,
        conditions=[_condition_out(condition) for condition in result.conditions],
        on_ferry=checkpoint.on_ferry,
    )


def _summary_out(route: PlannedRoute) -> RouteSummaryOut:
    summary = route.summary
    timeline = route.timeline
    return RouteSummaryOut(
        distance_km_by_level={level: _km(km) for level, km in summary.distance_km_by_level.items()},
        unknown_km=_km(summary.unknown_km),
        ferry_km=_km(summary.ferry_km),
        total_km=_km(summary.total_km),
        worst_level=summary.worst_level,
        blocking_km=_km(summary.blocking_km),
        average_risk=summary.average_risk,
        blocked=summary.blocked,
        driving_s=_seconds(timeline.driving_s),
        rest_s=_seconds(timeline.rest_s),
        ferry_s=_seconds(timeline.ferry_s),
        travel_time_s=_seconds(timeline.elapsed_s),
        arrival_utc=route.arrival_utc,
        warnings=list(summary.warnings),
    )


def _route_out(route: PlannedRoute, rank: int, ranking: Ranking) -> RouteOut:
    return RouteOut(
        id=route.route_id,
        rank=rank,
        recommended=route.route_id == ranking.recommended_id,
        best_available=route.route_id == ranking.best_available_id,
        not_recommendable_reason=ranking.not_recommendable.get(route.route_id),
        source=route.source,
        distance_km=_km(route.distance_km),
        polyline=route.polyline,
        summary=_summary_out(route),
        checkpoints=[_checkpoint_out(checkpoint) for checkpoint in route.checkpoints],
        stretches=[
            StretchOut(
                start_km=_km(item.stretch.start_km),
                end_km=_km(item.stretch.end_km),
                level=item.stretch.level,
                kind=item.stretch.kind,
                polyline=item.polyline,
            )
            for item in route.stretches
        ],
        stops=[
            StopOut(
                kind=item.stop.kind,
                distance_km=_km(item.stop.distance_km),
                latitude=_degrees(item.coordinate.latitude),
                longitude=_degrees(item.coordinate.longitude),
                start_utc=item.start_utc,
                duration_s=_seconds(item.stop.duration_s),
            )
            for item in route.stops
        ],
        positions_by_hour=[
            TruckPositionOut(
                hour=position.hour,
                distance_km=_km(position.distance_km),
                latitude=_degrees(position.coordinate.latitude),
                longitude=_degrees(position.coordinate.longitude),
            )
            for position in route.positions_by_hour
        ],
        refined_samples=route.refined_samples,
    )


def trip_out(plan: TripPlan) -> TripOut:
    """The response for a planned trip."""
    ranking = plan.ranking
    options = plan.options_used
    return TripOut(
        rule_set_version=plan.rule_set_version,
        stretch_method=plan.stretch_method,
        departure_utc=plan.departure_utc,
        vehicle_weight_kg=plan.vehicle_weight_kg,
        options_used=OptionsUsedOut(
            checkpoint_spacing_km=options.checkpoint_spacing_km,
            include_rest_stops=options.include_rest_stops,
            load_kg=options.load_kg,
        ),
        routes=[
            _route_out(route, rank, ranking) for rank, route in enumerate(plan.routes, start=1)
        ],
        ranking=RankingOut(
            key_names=list(RANKING_KEY_NAMES),
            keys=[
                RankingKeyOut(
                    route_id=key.route_id,
                    values=list(key.values),
                    has_known_weather=key.has_known_weather,
                )
                for key in ranking.keys
            ],
        ),
        recommended_route_id=ranking.recommended_id,
        no_recommendation_reason=ranking.no_recommendation_reason,
        best_available_route_id=ranking.best_available_id,
        routes_requested=plan.routes_requested,
        routes_found=plan.routes_found,
        fewer_routes_than_requested=plan.routes_found < plan.routes_requested,
        rounds_tried=list(plan.rounds_tried),
        warnings=list(plan.warnings),
        weather=WeatherReportOut(
            cell_size_deg=plan.weather.cell_size_deg,
            cells_requested=plan.weather.cells_requested,
            cells_missing=plan.weather.cells_missing,
            unknown_checkpoints=plan.weather.unknown_checkpoints,
            refined_samples=plan.weather.refined_samples,
        ),
    )
