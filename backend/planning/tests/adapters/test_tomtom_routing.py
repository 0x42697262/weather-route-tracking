import copy
import json
import logging
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import httpx
import pytest
from django.conf import settings

from planning.adapters.tomtom.client import TomTomRouteProvider, build_tomtom_route_provider
from planning.adapters.tomtom.protocol import parse_routes, route_path, route_query
from planning.domain.values import (
    Avoidance,
    Coordinate,
    PointRange,
    ProgressPoint,
    RouteRequest,
    Vehicle,
)
from planning.errors import NoRoadRoute, UpstreamInvalidResponse, UpstreamUnavailable
from planning.tests.adapters.support import (
    TEST_API_KEY,
    FakeTime,
    Recorder,
    fixture_json,
    fixture_text,
    make_retrier,
)

BASE_URL = "https://api.tomtom.example.com"
DALLAS = Coordinate(latitude=32.7767, longitude=-96.797)
DENTON = Coordinate(latitude=33.2148, longitude=-97.1331)
OKLAHOMA_CITY = Coordinate(latitude=35.4676, longitude=-97.5164)
DEPARTURE = datetime(2026, 11, 18, 14, 0, tzinfo=UTC)

type Handler = Callable[[httpx.Request], httpx.Response]


def _request(
    *,
    via: tuple[Coordinate, ...] = (),
    avoid: frozenset[Avoidance] = frozenset(),
    max_speed_kmh: float | None = 104.6,
    departure: datetime = DEPARTURE,
) -> RouteRequest:
    return RouteRequest(
        origin=DALLAS,
        destination=OKLAHOMA_CITY,
        departure_utc=departure,
        vehicle=Vehicle(weight_kg=34926.6, max_speed_kmh=max_speed_kmh),
        alternatives=4,
        avoid=avoid,
        via=via,
    )


@pytest.fixture
def fake_time() -> FakeTime:
    return FakeTime()


@pytest.fixture
async def make_provider(
    fake_time: FakeTime,
) -> AsyncIterator[Callable[[Recorder], TomTomRouteProvider]]:
    clients: list[httpx.AsyncClient] = []

    def build(recorder: Recorder) -> TomTomRouteProvider:
        client = httpx.AsyncClient(base_url=BASE_URL, transport=httpx.MockTransport(recorder))
        clients.append(client)
        return TomTomRouteProvider(client, TEST_API_KEY, make_retrier(fake_time))

    yield build
    for client in clients:
        await client.aclose()


def _ok(name: str) -> httpx.Response:
    return httpx.Response(200, text=fixture_text(name))


def test_path_lists_origin_via_points_and_destination() -> None:
    path = route_path(_request(via=(DENTON,)))

    assert path == (
        "/routing/1/calculateRoute/"
        "32.776700,-96.797000:33.214800,-97.133100:35.467600,-97.516400/json"
    )


def test_query_is_a_truck_request_in_metric_and_utc() -> None:
    eastern = timezone(timedelta(hours=-5))
    request = _request(
        avoid=frozenset({Avoidance.MOTORWAYS, Avoidance.TOLL_ROADS}),
        departure=datetime(2026, 11, 18, 9, 0, tzinfo=eastern),
    )

    query = route_query(request, TEST_API_KEY)

    assert query == [
        ("key", TEST_API_KEY),
        ("travelMode", "truck"),
        ("vehicleWeight", "34927"),
        ("vehicleMaxSpeed", "105"),
        ("vehicleCommercial", "true"),
        ("maxAlternatives", "4"),
        ("alternativeType", "anyRoute"),
        ("avoid", "motorways"),
        ("avoid", "tollRoads"),
        ("departAt", "2026-11-18T14:00:00+00:00"),
        ("sectionType", "ferry"),
        ("extendedRouteRepresentation", "travelTime"),
        ("extendedRouteRepresentation", "distance"),
        ("routeRepresentation", "polyline"),
    ]


def test_query_omits_max_speed_when_there_is_no_cap() -> None:
    names = [name for name, _ in route_query(_request(max_speed_kmh=None), TEST_API_KEY)]

    assert "vehicleMaxSpeed" not in names


def test_query_caps_alternatives_at_five() -> None:
    request = _request()
    many = RouteRequest(
        origin=request.origin,
        destination=request.destination,
        departure_utc=request.departure_utc,
        vehicle=request.vehicle,
        alternatives=9,
        avoid=request.avoid,
        via=request.via,
    )

    assert ("maxAlternatives", "5") in route_query(many, TEST_API_KEY)


def test_query_rejects_a_naive_departure() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        route_query(_request(departure=DEPARTURE.replace(tzinfo=None)), TEST_API_KEY)


async def test_routes_sends_one_get_and_parses_metric_routes(
    make_provider: Callable[[Recorder], TomTomRouteProvider],
) -> None:
    recorder = Recorder(_ok("tomtom_routes_dallas_oklahoma_city.json"))

    routes = await make_provider(recorder).routes(_request())

    sent = recorder.requests[0]
    assert sent.method == "GET"
    assert sent.url.path == route_path(_request())
    assert sent.url.params.get_list("extendedRouteRepresentation") == ["travelTime", "distance"]
    assert len(routes) == 2
    fastest = routes[0]
    assert len(fastest.points) == 203
    assert fastest.distance_km == pytest.approx(330.216)
    assert fastest.travel_time_s == 12438
    assert len(fastest.progress) == 50
    assert fastest.progress[0] == ProgressPoint(point_index=0, distance_km=0.0, elapsed_s=0.0)
    assert fastest.progress[-1].point_index == 202
    assert fastest.progress[-1].distance_km == pytest.approx(330.216)
    assert fastest.progress[-1].elapsed_s == 12438
    assert fastest.progress[1].distance_km == pytest.approx(0.229)
    assert fastest.ferry_sections == ()
    assert routes[1].distance_km == pytest.approx(456.265)


def test_ferry_sections_are_kept() -> None:
    (route,) = parse_routes(fixture_json("tomtom_route_manila_cebu_ferry.json"))

    assert route.ferry_sections == (
        PointRange(start_index=30, end_index=53),
        PointRange(start_index=117, end_index=121),
    )
    assert route.distance_km == pytest.approx(778.143)
    assert route.travel_time_s == 61995


def test_legs_are_joined_without_the_repeated_joint_point() -> None:
    (route,) = parse_routes(fixture_json("tomtom_route_dallas_via_denton.json"))

    joint = Coordinate(latitude=33.21453, longitude=-97.13311)
    assert len(route.points) == 476
    assert route.points[200] == joint
    assert route.points[201] != joint
    by_index = {entry.point_index: entry for entry in route.progress}
    assert by_index[200].distance_km == pytest.approx(79.016)
    assert by_index[201].distance_km == pytest.approx(79.075)
    assert route.progress[-1].point_index == 475
    assert route.progress[-1].distance_km == pytest.approx(424.168)
    indexes = [entry.point_index for entry in route.progress]
    assert indexes == sorted(set(indexes))


def test_missing_progress_ends_are_synthesized_from_the_summary() -> None:
    payload = copy.deepcopy(fixture_json("tomtom_routes_dallas_oklahoma_city.json"))
    assert isinstance(payload, dict)
    del payload["routes"][0]["progress"]

    route = parse_routes(payload)[0]

    first, last = route.progress
    assert first == ProgressPoint(point_index=0, distance_km=0.0, elapsed_s=0.0)
    assert (last.point_index, last.elapsed_s) == (202, 12438)
    assert last.distance_km == pytest.approx(330.216)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["routes"].clear(),
        lambda payload: payload["routes"][0]["legs"][0]["points"][0].update(latitude=91),
        lambda payload: payload["routes"][0]["progress"][3].update(distanceInMeters=10**9),
        lambda payload: payload["routes"][0]["progress"][3].update(pointIndex=10**6),
        lambda payload: payload["routes"][0].pop("summary"),
    ],
    ids=[
        "no-routes",
        "latitude-out-of-range",
        "distance-goes-back",
        "index-past-end",
        "no-summary",
    ],
)
def test_malformed_routes_are_rejected(mutate: Callable[[dict[str, Any]], object]) -> None:
    payload = copy.deepcopy(fixture_json("tomtom_routes_dallas_oklahoma_city.json"))
    assert isinstance(payload, dict)
    mutate(payload)

    with pytest.raises(UpstreamInvalidResponse):
        parse_routes(payload)


async def test_no_route_found_is_no_road_route(
    make_provider: Callable[[Recorder], TomTomRouteProvider],
) -> None:
    recorder = Recorder(httpx.Response(400, text=fixture_text("tomtom_no_route_found.json")))

    with pytest.raises(NoRoadRoute):
        await make_provider(recorder).routes(_request())

    assert len(recorder.requests) == 1


async def test_other_400_is_unavailable(
    make_provider: Callable[[Recorder], TomTomRouteProvider],
) -> None:
    body = {"detailedError": {"code": "BAD_INPUT", "message": "x"}}
    recorder = Recorder(httpx.Response(400, json=body))

    with pytest.raises(UpstreamUnavailable):
        await make_provider(recorder).routes(_request())


async def test_unparseable_body_is_invalid(
    make_provider: Callable[[Recorder], TomTomRouteProvider],
) -> None:
    recorder = Recorder(httpx.Response(200, text="<html>oops</html>"))

    with pytest.raises(UpstreamInvalidResponse):
        await make_provider(recorder).routes(_request())


async def test_timeout_is_unavailable_after_retries(
    make_provider: Callable[[Recorder], TomTomRouteProvider],
) -> None:
    recorder = Recorder(*[httpx.ReadTimeout("slow")] * 3)

    with pytest.raises(UpstreamUnavailable):
        await make_provider(recorder).routes(_request())

    assert len(recorder.requests) == 3


async def test_429_with_retry_after_then_success(
    make_provider: Callable[[Recorder], TomTomRouteProvider], fake_time: FakeTime
) -> None:
    recorder = Recorder(
        httpx.Response(429, headers={"Retry-After": "1"}),
        _ok("tomtom_routes_dallas_oklahoma_city.json"),
    )

    routes = await make_provider(recorder).routes(_request())

    assert len(routes) == 2
    assert fake_time.sleeps == [1.0]


async def test_503_then_success(
    make_provider: Callable[[Recorder], TomTomRouteProvider], fake_time: FakeTime
) -> None:
    recorder = Recorder(httpx.Response(503), _ok("tomtom_routes_dallas_oklahoma_city.json"))

    routes = await make_provider(recorder).routes(_request())

    assert len(routes) == 2
    assert fake_time.sleeps == [0.5]


def test_capabilities(make_provider: Callable[[Recorder], TomTomRouteProvider]) -> None:
    provider = make_provider(Recorder())

    assert provider.supported_avoidances == frozenset(Avoidance)
    assert provider.supports_via is True
    assert provider.max_alternatives == 5


async def test_factory_uses_settings_and_never_logs_the_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    recorder = Recorder(httpx.Response(503), _ok("tomtom_routes_dallas_oklahoma_city.json"))
    provider = build_tomtom_route_provider(settings.APP_ENV, httpx.MockTransport(recorder))
    secret = settings.APP_ENV.tomtom_api_key
    assert secret is not None
    key = secret.get_secret_value()

    try:
        routes = await provider.routes(_request())
    finally:
        await provider.aclose()

    assert len(routes) == 2
    assert recorder.requests[0].url.host == settings.APP_ENV.tomtom_base_url.host
    logged = json.dumps([record.__dict__ for record in caplog.records], default=str)
    assert "upstream.retry" in logged
    assert key not in logged
