"""Calls to the real providers, opt-in.

Run: `uv run --env-file ../.env pytest -m live planning/tests/adapters`.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from django.conf import settings

from planning.adapters.open_meteo.client import build_open_meteo_weather_provider
from planning.adapters.tomtom.client import build_tomtom_geocoder, build_tomtom_route_provider
from planning.domain.values import Coordinate, RouteRequest, Vehicle
from planning.errors import NoRoadRoute
from shared.weather_variables import WeatherVariable

pytestmark = pytest.mark.live

DALLAS = Coordinate(latitude=32.7767, longitude=-96.797)
OKLAHOMA_CITY = Coordinate(latitude=35.4676, longitude=-97.5164)
BASCO = Coordinate(latitude=20.4487, longitude=121.9702)
MANILA = Coordinate(latitude=14.5995, longitude=120.9842)


def _request(origin: Coordinate, destination: Coordinate) -> RouteRequest:
    departure = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)
    return RouteRequest(
        origin=origin,
        destination=destination,
        departure_utc=departure,
        vehicle=Vehicle(weight_kg=34927, max_speed_kmh=105),
        alternatives=2,
        avoid=frozenset(),
        via=(),
    )


async def test_tomtom_routes_a_truck() -> None:
    provider = build_tomtom_route_provider(settings.APP_ENV)
    try:
        routes = await provider.routes(_request(DALLAS, OKLAHOMA_CITY))
    finally:
        await provider.aclose()

    fastest = routes[0]
    assert 300 < fastest.distance_km < 400
    assert fastest.progress[0].point_index == 0
    assert fastest.progress[-1].point_index == len(fastest.points) - 1


async def test_tomtom_reports_no_road_route() -> None:
    provider = build_tomtom_route_provider(settings.APP_ENV)
    try:
        with pytest.raises(NoRoadRoute):
            await provider.routes(_request(BASCO, MANILA))
    finally:
        await provider.aclose()


async def test_tomtom_places_suggest_then_details() -> None:
    geocoder = build_tomtom_geocoder(settings.APP_ENV)
    try:
        suggestions = await geocoder.suggest("Dal", str(uuid.uuid4()))
        place = await geocoder.details(suggestions[0].place_id)
    finally:
        await geocoder.aclose()

    assert suggestions[0].title.startswith("Dallas")
    assert place.coordinate.latitude == pytest.approx(32.78, abs=0.2)
    assert place.coordinate.longitude == pytest.approx(-96.8, abs=0.2)


async def test_open_meteo_forecasts_two_cells() -> None:
    provider = build_open_meteo_weather_provider(settings.APP_ENV)
    cells = [Coordinate(latitude=35.5, longitude=-97.5), Coordinate(latitude=32.8, longitude=-96.8)]
    try:
        forecasts = await provider.forecasts(cells, frozenset(WeatherVariable), datetime.now(UTC))
    finally:
        await provider.aclose()

    assert set(forecasts) == set(cells)
    assert all(
        len(forecast.hours_utc) >= provider.forecast_horizon_hours
        for forecast in forecasts.values()
    )
