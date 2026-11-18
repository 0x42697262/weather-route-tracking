import itertools
from datetime import timedelta

import pytest
from django.core.cache.backends.locmem import LocMemCache

from planning.adapters.forecast_cache import CachingWeatherProvider
from planning.adapters.tomtom.protocol import parse_routes
from planning.domain.geometry import decode_polyline, haversine_km
from planning.domain.ranking import NoRecommendationReason
from planning.domain.risk_constants import FORECAST_WINDOW_HOURS
from planning.domain.summary import RouteWarning
from planning.domain.values import Coordinate, RouteSource
from planning.errors import (
    InvalidRequest,
    NoRoadRoute,
    PlanningError,
    Rejection,
    TripOptionsInvalid,
)
from planning.services.limits import PlanningLimits
from planning.services.plan_trip import TripPlan, TripRequest, TripWarning, plan_trip
from planning.tests.adapters.support import fixture_json
from planning.tests.services.support import (
    CHICAGO,
    DALLAS,
    DENVER,
    DEPARTURE,
    LIMITS,
    NO_TRAVEL_WIND,
    NOW,
    REFINE_RULE_SET,
    RULE_SET,
    SEVERE_WIND,
    RecordingCache,
    RecordingWeather,
    ScriptedRoutes,
    north_of,
    route,
    trip,
)
from rulesets.domain.defaults import default_rule_set_document
from rulesets.domain.schema import VersionedRuleSet
from rulesets.domain.validator import validate_rule_set
from shared.risk_levels import RiskLevel

DEFAULT_MAX_UNKNOWN_SHARE = validate_rule_set(default_rule_set_document()).max_unknown_share or 0.0

THREE_ROUTES = (
    route(),
    route(bow_share=0.15, speed_kmh=80.0),
    route(bow_share=-0.2, speed_kmh=78.0),
)
REST_OFF_DUTY_S = 10 * 3600


async def plan(
    request: TripRequest,
    routes: ScriptedRoutes | None = None,
    weather: RecordingWeather | CachingWeatherProvider | None = None,
    rule_set: VersionedRuleSet = RULE_SET,
    limits: PlanningLimits = LIMITS,
) -> TripPlan:
    return await plan_trip(
        request,
        routes=routes or ScriptedRoutes([THREE_ROUTES]),
        route_provider_name="scripted",
        weather=weather or RecordingWeather(),
        rule_set=rule_set,
        limits=limits,
        now_utc=NOW,
    )


async def test_a_normal_plan_has_three_ranked_routes_with_everything_to_draw() -> None:
    weather = RecordingWeather()

    result = await plan(trip(), weather=weather)

    assert result.routes_found == result.routes_requested == 3
    assert result.ranking.recommended_id == result.routes[0].route_id
    assert result.warnings == ()
    assert result.rule_set_version == 1
    assert len(weather.calls) == 1
    assert result.weather.cells_requested == len(set(weather.cells_seen))
    for planned in result.routes:
        checkpoints = planned.checkpoints
        assert checkpoints[0].distance_km == 0
        assert checkpoints[-1].distance_km == pytest.approx(planned.distance_km)
        assert all(point.level is RiskLevel.LOW for point in checkpoints)
        arrivals = [point.arrival_utc for point in checkpoints]
        assert arrivals[0] == DEPARTURE
        assert arrivals == sorted(arrivals)
        assert planned.summary.total_km == pytest.approx(planned.distance_km)
        assert len(planned.positions_by_hour) == FORECAST_WINDOW_HOURS + 1
        assert planned.positions_by_hour[0].coordinate == planned.checkpoints[0].coordinate
        assert planned.positions_by_hour[-1].distance_km == pytest.approx(planned.distance_km)
        assert len(decode_polyline(planned.polyline)) >= 2
        assert planned.stretches[0].stretch.start_km == 0


async def test_the_first_routes_are_labeled_by_source() -> None:
    result = await plan(trip())

    assert {planned.source for planned in result.routes} == {
        RouteSource.FASTEST,
        RouteSource.ALTERNATIVE,
    }
    assert result.rounds_tried == (RouteSource.FASTEST,)


@pytest.mark.parametrize(
    ("request_", "error", "reason"),
    [
        (trip(spacing_km=30.0), TripOptionsInvalid, None),
        (trip(load_kg=60000.0), TripOptionsInvalid, None),
        (trip(load_kg=None), TripOptionsInvalid, None),
        (trip(include_rest_stops=None, load_kg=-1.0), TripOptionsInvalid, None),
        (
            trip(departure_utc=NOW - timedelta(hours=1)),
            InvalidRequest,
            Rejection.DEPARTURE_OUT_OF_RANGE,
        ),
        (
            trip(departure_utc=NOW + timedelta(hours=97)),
            InvalidRequest,
            Rejection.DEPARTURE_OUT_OF_RANGE,
        ),
        (trip(destination=DALLAS), InvalidRequest, Rejection.SAME_PLACE),
        (
            trip(destination=Coordinate(52.52, 13.405)),
            InvalidRequest,
            Rejection.TRIP_TOO_LONG,
        ),
        (
            trip(origin=CHICAGO, destination=DENVER, spacing_km=16.09344),
            InvalidRequest,
            Rejection.TOO_MANY_WEATHER_CELLS,
        ),
    ],
)
async def test_local_rejections_call_no_provider(
    request_: TripRequest, error: type[PlanningError], reason: Rejection | None
) -> None:
    routes = ScriptedRoutes([THREE_ROUTES])
    weather = RecordingWeather()
    limits = PlanningLimits(
        trip_max_distance_km=3000.0,
        max_checkpoints_per_route=200,
        route_alternatives_requested=4,
        route_max_extra_requests=4,
        weather_max_cells=80,
    )

    with pytest.raises(error) as caught:
        await plan(request_, routes, weather, limits=limits)

    assert routes.requests == []
    assert weather.calls == []
    if reason is not None:
        assert isinstance(caught.value, InvalidRequest)
        assert caught.value.reason is reason


async def test_a_departure_just_inside_the_tolerance_is_accepted() -> None:
    result = await plan(trip(departure_utc=NOW - timedelta(minutes=14)))

    assert result.routes_found == 3


async def test_too_many_weather_cells_after_routing_is_rejected_before_any_weather_call() -> None:
    weather = RecordingWeather()
    limits = PlanningLimits(
        trip_max_distance_km=3000.0,
        max_checkpoints_per_route=200,
        route_alternatives_requested=4,
        route_max_extra_requests=4,
        weather_max_cells=12,
    )

    with pytest.raises(InvalidRequest) as caught:
        await plan(trip(), weather=weather, limits=limits)

    assert caught.value.reason is Rejection.TOO_MANY_WEATHER_CELLS
    assert weather.calls == []


async def test_no_road_route_is_raised() -> None:
    weather = RecordingWeather()

    with pytest.raises(NoRoadRoute):
        await plan(trip(), ScriptedRoutes([NoRoadRoute()]), weather)

    assert weather.calls == []


@pytest.mark.parametrize("kept", [1, 2])
async def test_rounds_exhausted_with_fewer_routes_is_a_normal_result(kept: int) -> None:
    answers: list[object] = [THREE_ROUTES[:kept]]
    answers.extend([(THREE_ROUTES[0],)] * 4)
    routes = ScriptedRoutes(answers)  # type: ignore[arg-type]

    result = await plan(trip(), routes)

    assert result.routes_found == kept
    assert TripWarning.FEWER_ROUTES_THAN_TARGET in result.warnings
    assert result.ranking.recommended_id is not None


async def test_partial_weather_gives_unknown_checkpoints_and_a_warning() -> None:
    weather = RecordingWeather(fails=lambda cell: cell.latitude > 34.5)

    result = await plan(trip(), weather=weather)

    assert TripWarning.WEATHER_PARTIAL in result.warnings
    assert result.weather.cells_missing > 0
    assert result.weather.unknown_checkpoints > 0
    first = result.routes[0]
    assert any(point.level is None for point in first.checkpoints)
    assert RouteWarning.UNKNOWN_WEATHER in first.summary.warnings
    assert first.summary.unknown_km > 0


async def test_too_much_unknown_weather_blocks_the_recommendation_with_its_reason() -> None:
    weather = RecordingWeather(fails=lambda cell: cell.latitude > 33.5)

    result = await plan(trip(), weather=weather)

    shares = [route.summary.unknown_km / route.summary.total_km for route in result.routes]
    assert min(shares) > DEFAULT_MAX_UNKNOWN_SHARE
    assert result.ranking.recommended_id is None
    assert (
        result.ranking.no_recommendation_reason is NoRecommendationReason.TOO_MUCH_UNKNOWN_WEATHER
    )


async def test_all_weather_missing_gives_no_recommendation() -> None:
    result = await plan(trip(), weather=RecordingWeather(fails=lambda _cell: True))

    assert result.ranking.recommended_id is None
    assert result.ranking.no_recommendation_reason is NoRecommendationReason.NO_KNOWN_WEATHER
    assert TripWarning.WEATHER_UNAVAILABLE in result.warnings
    assert result.routes_found == 3


async def test_every_route_with_no_travel_gives_no_recommendation() -> None:
    weather = RecordingWeather(pattern=north_of(34.0, NO_TRAVEL_WIND))

    result = await plan(trip(), weather=weather)

    assert result.ranking.recommended_id is None
    assert result.ranking.no_recommendation_reason is NoRecommendationReason.EVERY_ROUTE_BLOCKED
    assert all(planned.summary.blocked for planned in result.routes)
    assert len(result.routes) == 3


async def test_a_second_identical_request_fetches_no_forecast_cell_again() -> None:
    inner = RecordingWeather()
    cache = LocMemCache("plan-trip-second-request", {})
    weather = CachingWeatherProvider(inner, cache, 600)

    first = await plan(trip(), ScriptedRoutes([THREE_ROUTES]), weather)
    second = await plan(trip(), ScriptedRoutes([THREE_ROUTES]), weather)

    assert len(inner.calls) == 1
    assert first.ranking == second.ranking


async def test_nothing_from_the_route_provider_is_written_to_the_cache() -> None:
    cache = RecordingCache("plan-trip-nothing-cached")
    weather = CachingWeatherProvider(RecordingWeather(), cache, 600)

    await plan(trip(), weather=weather)

    assert cache.written
    assert all(key.startswith("forecast:") for key in cache.written)


async def test_refine_adds_samples_only_where_levels_differ() -> None:
    calm = await plan(trip(), rule_set=REFINE_RULE_SET)
    assert calm.weather.refined_samples == 0

    pattern = north_of(34.0, SEVERE_WIND)
    light = trip(load_kg=10000.0)
    coarse = await plan(light, weather=RecordingWeather(pattern=pattern))
    fine = await plan(light, weather=RecordingWeather(pattern=pattern), rule_set=REFINE_RULE_SET)

    assert 0 < fine.weather.refined_samples <= 3 * 4
    fine_by_id = {planned.route_id: planned for planned in fine.routes}
    shrunk = 0
    for coarse_route in coarse.routes:
        fine_route = fine_by_id[coarse_route.route_id]
        coarse_km = coarse_route.summary.distance_km_by_level[RiskLevel.SEVERE]
        fine_km = fine_route.summary.distance_km_by_level[RiskLevel.SEVERE]
        assert fine_km <= coarse_km
        shrunk += fine_km < coarse_km
        assert len(fine_route.checkpoints) == len(coarse_route.checkpoints)
    assert shrunk >= 1
    assert fine.stretch_method.value == "refine"


async def test_rest_stops_change_arrival_times_on_a_long_trip() -> None:
    long_trip = (route(CHICAGO, DENVER),)

    rested = await plan(
        trip(CHICAGO, DENVER, include_rest_stops=True), ScriptedRoutes([long_trip] * 5)
    )
    straight = await plan(
        trip(CHICAGO, DENVER, include_rest_stops=False), ScriptedRoutes([long_trip] * 5)
    )

    with_rest = rested.routes[0]
    without_rest = straight.routes[0]
    assert with_rest.stops
    assert with_rest.timeline.rest_s >= REST_OFF_DUTY_S
    assert with_rest.arrival_utc > without_rest.arrival_utc
    assert with_rest.checkpoints[-1].arrival_utc > without_rest.checkpoints[-1].arrival_utc
    assert without_rest.stops == ()
    assert rested.options_used.include_rest_stops is True


async def test_rest_on_and_off_are_identical_under_eight_hours() -> None:
    on = await plan(trip(include_rest_stops=True))
    off = await plan(trip(include_rest_stops=False))

    for on_route, off_route in zip(on.routes, off.routes, strict=True):
        assert [point.arrival_utc for point in on_route.checkpoints] == [
            point.arrival_utc for point in off_route.checkpoints
        ]
        assert on_route.stops == ()


async def test_rest_stops_default_to_the_rule_set_switch() -> None:
    result = await plan(trip())

    assert result.options_used.include_rest_stops is RULE_SET.rules.rest_rules.enabled


async def test_a_gross_weight_over_the_federal_limit_is_warned() -> None:
    light = await plan(trip(load_kg=20000.0))
    heavy = await plan(trip(load_kg=25000.0))

    assert TripWarning.GROSS_WEIGHT_OVER_LIMIT not in light.warnings
    assert TripWarning.GROSS_WEIGHT_OVER_LIMIT in heavy.warnings
    assert heavy.routes_found == 3


async def test_vehicle_weight_and_speed_go_to_the_route_provider() -> None:
    routes = ScriptedRoutes([THREE_ROUTES])

    await plan(trip(load_kg=10000.0), routes)

    vehicle = routes.requests[0].vehicle
    rules = RULE_SET.rules
    assert vehicle.weight_kg == pytest.approx(rules.empty_vehicle_weight_kg + 10000.0)
    assert vehicle.max_speed_kmh == rules.truck_max_speed_kmh
    assert routes.requests[0].departure_utc == DEPARTURE


async def test_recorded_tomtom_routes_plan_with_fake_weather() -> None:
    recorded = parse_routes(fixture_json("tomtom_routes_dallas_oklahoma_city.json"))
    origin = recorded[0].points[0]
    destination = recorded[0].points[-1]
    routes = ScriptedRoutes([recorded, *itertools.repeat((recorded[0],), 4)])

    result = await plan(trip(origin, destination), routes, RecordingWeather())

    assert result.routes_found >= 1
    first = result.routes[0]
    assert first.source is RouteSource.FASTEST
    assert first.distance_km == pytest.approx(recorded[0].distance_km, rel=0.02)
    assert first.checkpoints[-1].coordinate == destination
    assert result.ranking.recommended_id is not None


async def test_a_recorded_ferry_route_counts_ferry_distance() -> None:
    recorded = parse_routes(fixture_json("tomtom_route_manila_cebu_ferry.json"))
    origin = recorded[0].points[0]
    destination = recorded[0].points[-1]
    routes = ScriptedRoutes([recorded, *itertools.repeat(recorded, 4)])

    result = await plan(trip(origin, destination), routes)

    ferry = result.routes[0]
    assert ferry.summary.ferry_km > 0
    assert RouteWarning.FERRY_CROSSING in ferry.summary.warnings
    assert ferry.timeline.ferry_s > 0
    assert haversine_km(origin, destination) < ferry.distance_km
