import pytest

from planning.domain.geometry import measure_line
from planning.domain.values import (
    Avoidance,
    Coordinate,
    ProgressPoint,
    ProviderRoute,
    RouteRequest,
    RouteSource,
    Vehicle,
)
from planning.errors import InvalidRequest, NoRoadRoute, Rejection, UpstreamUnavailable
from planning.services.route_options import RouteBounds, RouteSearch, find_routes
from planning.tests.services.support import (
    CHICAGO,
    DALLAS,
    DENVER,
    DEPARTURE,
    OKLAHOMA_CITY,
    ScriptedRoutes,
    route,
)

BOUNDS = RouteBounds(max_distance_km=3000.0, spacing_km=40.2336, max_checkpoints=200)
FASTEST = route()
NORTH = route(bow_share=0.15, speed_kmh=80.0)
SOUTH = route(bow_share=-0.2, speed_kmh=78.0)
FAR_SOUTH = route(bow_share=-0.35, speed_kmh=75.0)
REPEAT = route(speed_kmh=84.0)
CRAWL = route(bow_share=0.3, speed_kmh=30.0)


def base(origin: Coordinate = DALLAS, destination: Coordinate = OKLAHOMA_CITY) -> RouteRequest:
    return RouteRequest(
        origin=origin,
        destination=destination,
        departure_utc=DEPARTURE,
        vehicle=Vehicle(weight_kg=30000.0, max_speed_kmh=104.6),
        alternatives=0,
        avoid=frozenset(),
        via=(),
    )


async def search(
    provider: ScriptedRoutes, request: RouteRequest | None = None, max_extra: int = 4
) -> RouteSearch:
    return await find_routes(
        provider,
        "scripted",
        request or base(),
        BOUNDS,
        alternatives_requested=4,
        max_extra_requests=max_extra,
    )


def sources(result: RouteSearch) -> list[RouteSource]:
    return [kept.source for kept in result.routes]


async def test_three_routes_in_the_first_answer_need_no_extra_request() -> None:
    provider = ScriptedRoutes([(FASTEST, NORTH, SOUTH)])

    result = await search(provider)

    assert len(provider.requests) == 1
    assert provider.requests[0].alternatives == 4
    assert sources(result) == [
        RouteSource.FASTEST,
        RouteSource.ALTERNATIVE,
        RouteSource.ALTERNATIVE,
    ]
    assert result.rounds_tried == (RouteSource.FASTEST,)
    assert result.extra_requests == 0


async def test_alternatives_asked_are_capped_at_the_provider_maximum() -> None:
    provider = ScriptedRoutes([(FASTEST, NORTH, SOUTH)], max_alternatives=2)

    await search(provider)

    assert provider.requests[0].alternatives == 2


async def test_rounds_run_in_order_drop_repeats_and_slow_routes_and_stop_at_three() -> None:
    provider = ScriptedRoutes([(FASTEST,), (REPEAT,), (CRAWL,), (NORTH,), (SOUTH,)])

    result = await search(provider)

    sent = provider.requests[1:]
    assert [request.avoid for request in sent] == [
        frozenset({Avoidance.TOLL_ROADS}),
        frozenset({Avoidance.MOTORWAYS}),
        frozenset(),
        frozenset(),
    ]
    assert [len(request.via) for request in sent] == [0, 0, 1, 1]
    assert all(request.alternatives == 0 for request in sent)
    assert sources(result) == [RouteSource.FASTEST, RouteSource.DETOUR, RouteSource.DETOUR]
    assert result.rounds_tried == (
        RouteSource.FASTEST,
        RouteSource.AVOID_TOLLS,
        RouteSource.AVOID_HIGHWAYS,
        RouteSource.DETOUR,
    )


async def test_the_search_stops_as_soon_as_three_are_kept() -> None:
    provider = ScriptedRoutes([(FASTEST, NORTH), (SOUTH,)])

    result = await search(provider)

    assert len(provider.requests) == 2
    assert sources(result)[-1] is RouteSource.AVOID_TOLLS


async def test_unsupported_rounds_are_skipped() -> None:
    provider = ScriptedRoutes(
        [(FASTEST,), (NORTH,)],
        supported_avoidances=frozenset({Avoidance.MOTORWAYS}),
        supports_via=False,
    )

    result = await search(provider)

    assert [request.avoid for request in provider.requests[1:]] == [
        frozenset({Avoidance.MOTORWAYS})
    ]
    assert sources(result) == [RouteSource.FASTEST, RouteSource.AVOID_HIGHWAYS]


async def test_the_extra_request_cap_holds() -> None:
    provider = ScriptedRoutes([(FASTEST,), (REPEAT,), (REPEAT,)])

    result = await search(provider, max_extra=1)

    assert len(provider.requests) == 2
    assert result.extra_requests == 1
    assert len(result.routes) == 1


async def test_a_failing_top_up_request_is_skipped() -> None:
    provider = ScriptedRoutes([(FASTEST,), UpstreamUnavailable(), (NORTH,), (SOUTH,)])

    result = await search(provider)

    assert sources(result) == [
        RouteSource.FASTEST,
        RouteSource.AVOID_HIGHWAYS,
        RouteSource.DETOUR,
    ]


async def test_the_motorway_round_is_skipped_for_a_long_fastest_route() -> None:
    long_fastest = route(CHICAGO, DENVER)
    provider = ScriptedRoutes([(long_fastest,), (long_fastest,), (long_fastest,), (long_fastest,)])

    await search(provider, base(CHICAGO, DENVER))

    assert all(Avoidance.MOTORWAYS not in request.avoid for request in provider.requests)
    assert len(provider.requests) == 4


async def test_exhausted_rounds_return_what_was_kept() -> None:
    provider = ScriptedRoutes([(FASTEST, NORTH), (REPEAT,), (REPEAT,), (CRAWL,), (REPEAT,)])

    result = await search(provider)

    assert sources(result) == [RouteSource.FASTEST, RouteSource.ALTERNATIVE]
    assert result.extra_requests == 4


async def test_no_road_route_from_the_first_request_is_raised() -> None:
    with pytest.raises(NoRoadRoute):
        await search(ScriptedRoutes([NoRoadRoute()]))


async def test_an_empty_first_answer_is_no_road_route() -> None:
    with pytest.raises(NoRoadRoute):
        await search(ScriptedRoutes([()]))


async def test_a_fastest_route_over_the_maximum_is_rejected() -> None:
    provider = ScriptedRoutes([(FASTEST,)])
    short = RouteBounds(max_distance_km=100.0, spacing_km=40.2336, max_checkpoints=200)

    with pytest.raises(InvalidRequest) as caught:
        await find_routes(
            provider,
            "scripted",
            base(),
            short,
            alternatives_requested=4,
            max_extra_requests=4,
        )

    assert caught.value.reason is Rejection.TRIP_TOO_LONG


async def test_a_fastest_route_needing_too_many_checkpoints_is_rejected() -> None:
    tight = RouteBounds(max_distance_km=3000.0, spacing_km=1.0, max_checkpoints=50)

    with pytest.raises(InvalidRequest) as caught:
        await find_routes(
            ScriptedRoutes([(FASTEST,)]),
            "scripted",
            base(),
            tight,
            alternatives_requested=4,
            max_extra_requests=4,
        )

    assert caught.value.reason is Rejection.TOO_MANY_CHECKPOINTS
    assert caught.value.details[0].field == "checkpoint_spacing"


async def test_an_alternative_over_the_maximum_is_dropped() -> None:
    length_km = FASTEST.distance_km
    bounds = RouteBounds(max_distance_km=length_km * 1.02, spacing_km=40.2336, max_checkpoints=200)

    result = await find_routes(
        ScriptedRoutes(
            [(FASTEST, FAR_SOUTH)], supports_via=False, supported_avoidances=frozenset()
        ),
        "scripted",
        base(),
        bounds,
        alternatives_requested=4,
        max_extra_requests=4,
    )

    assert sources(result) == [RouteSource.FASTEST]


def _route_through(points: list[Coordinate], speed_kmh: float = 85.0) -> ProviderRoute:
    line = measure_line(points)
    seconds_per_km = 3600.0 / speed_kmh
    return ProviderRoute(
        points=line.points,
        distance_km=line.length_km,
        travel_time_s=line.length_km * seconds_per_km,
        progress=tuple(
            ProgressPoint(point_index=index, distance_km=km, elapsed_s=km * seconds_per_km)
            for index, km in enumerate(line.cumulative_km)
        ),
        ferry_sections=(),
    )


def _mostly_fastest(shared_share: float) -> ProviderRoute:
    split = int(len(FASTEST.points) * shared_share)
    tail = route(origin=FASTEST.points[split], bow_share=0.3)
    return _route_through([*FASTEST.points[:split], *tail.points[1:]])


SIMILAR = _mostly_fastest(0.85)
SLOW_SOUTH = route(bow_share=-0.2, speed_kmh=45.0)


async def test_a_similar_route_fills_the_third_place_when_the_rounds_run_out() -> None:
    provider = ScriptedRoutes([(FASTEST, NORTH), (SIMILAR,), (REPEAT,), (REPEAT,), (REPEAT,)])

    result = await search(provider)

    assert sources(result) == [RouteSource.FASTEST, RouteSource.ALTERNATIVE, RouteSource.SIMILAR]
    assert result.routes[2].route is SIMILAR


async def test_a_slower_route_fills_the_third_place_when_the_rounds_run_out() -> None:
    provider = ScriptedRoutes([(FASTEST, NORTH), (SLOW_SOUTH,), (REPEAT,), (REPEAT,), (REPEAT,)])

    result = await search(provider)

    assert sources(result) == [RouteSource.FASTEST, RouteSource.ALTERNATIVE, RouteSource.SLOWER]


async def test_the_most_different_set_aside_route_is_kept_first() -> None:
    provider = ScriptedRoutes([(FASTEST,), (SIMILAR,), (SLOW_SOUTH,), (REPEAT,), (REPEAT,)])

    result = await search(provider)

    assert sources(result) == [RouteSource.FASTEST, RouteSource.SLOWER, RouteSource.SIMILAR]


async def test_repeats_and_very_slow_routes_never_fill_a_place() -> None:
    provider = ScriptedRoutes([(FASTEST, NORTH, REPEAT), (CRAWL,), (REPEAT,), (REPEAT,), (CRAWL,)])

    result = await search(provider)

    assert sources(result) == [RouteSource.FASTEST, RouteSource.ALTERNATIVE]


async def test_distinct_routes_found_in_the_rounds_win_over_set_aside_ones() -> None:
    provider = ScriptedRoutes([(FASTEST, SIMILAR), (NORTH,), (SOUTH,)])

    result = await search(provider)

    assert sources(result) == [
        RouteSource.FASTEST,
        RouteSource.AVOID_TOLLS,
        RouteSource.AVOID_HIGHWAYS,
    ]
