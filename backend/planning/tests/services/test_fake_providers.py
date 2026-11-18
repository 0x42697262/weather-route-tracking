from planning.adapters.fake.places import FakeGeocoder
from planning.adapters.fake.routes import FakeRouteProvider
from planning.adapters.fake.weather import FakeWeatherProvider
from planning.domain.values import RouteSource
from planning.services.plan_trip import plan_trip
from planning.services.weather_grid import GridRequest, build_weather_grid
from planning.tests.services.support import (
    DEPARTURE,
    LIMITS,
    LOAD_KG,
    NOW,
    RULE_SET,
    trip,
)
from shared.risk_levels import RiskLevel

MIN_LEVELS_MET = 3


async def test_the_fake_trip_has_three_routes_and_meets_several_levels_with_no_travel() -> None:
    weather = FakeWeatherProvider()
    plan = await plan_trip(
        trip(),
        routes=FakeRouteProvider(),
        route_provider_name="fake",
        weather=weather,
        rule_set=RULE_SET,
        limits=LIMITS,
        now_utc=NOW,
    )
    lines = tuple(route.polyline for route in plan.routes)
    grid = await build_weather_grid(
        GridRequest(lines, DEPARTURE, LOAD_KG),
        weather=weather,
        rule_set=RULE_SET,
        limits=LIMITS,
        now_utc=NOW,
    )

    assert plan.routes_found == len(plan.routes) == 3
    assert {route.source for route in plan.routes} == {
        RouteSource.FASTEST,
        RouteSource.ALTERNATIVE,
    }
    met = {level for cell in grid.grid.cells for level in cell.combined if level is not None}
    assert len(met) >= MIN_LEVELS_MET
    assert RiskLevel.NO_TRAVEL in met


async def test_the_fake_geocoder_finds_dallas_and_its_details() -> None:
    geocoder = FakeGeocoder()

    suggestions = await geocoder.suggest("Dallas", "session")
    place = await geocoder.details(suggestions[0].place_id)

    assert place.label.startswith("Dallas")
