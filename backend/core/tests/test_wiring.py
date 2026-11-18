import pytest

from core.env import load_env
from core.provider_names import GeocoderName, RouteProviderName, WeatherProviderName
from core.tests.test_env import VALID_ENVIRONMENT
from core.wiring import (
    GEOCODERS,
    ROUTE_PROVIDERS,
    WEATHER_PROVIDERS,
    build_limits,
    build_providers,
)
from planning.adapters.fake.places import FakeGeocoder
from planning.adapters.fake.routes import FakeRouteProvider
from planning.adapters.forecast_cache import CachingWeatherProvider
from planning.adapters.tomtom.client import TomTomRouteProvider


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for variable, value in VALID_ENVIRONMENT.items():
        monkeypatch.setenv(variable, value)
    return monkeypatch


def test_every_provider_name_has_a_wiring_entry() -> None:
    assert set(ROUTE_PROVIDERS) == set(RouteProviderName)
    assert set(GEOCODERS) == set(GeocoderName)
    assert set(WEATHER_PROVIDERS) == set(WeatherProviderName)


async def test_the_default_providers_are_tomtom_and_cached_open_meteo(
    environment: pytest.MonkeyPatch,
) -> None:
    providers = build_providers(load_env())

    assert isinstance(providers.routes, TomTomRouteProvider)
    assert isinstance(providers.weather, CachingWeatherProvider)
    assert providers.route_provider_name == "tomtom"
    assert [item.text for item in providers.attributions] == [
        "\u00a9TomTom",
        "\u00a9TomTom, \u00a9OpenStreetMap",
        "Weather data by Open-Meteo.com",
    ]


async def test_fake_providers_need_no_key(environment: pytest.MonkeyPatch) -> None:
    environment.delenv("TOMTOM_API_KEY")
    for variable in ("ROUTE_PROVIDER", "GEOCODER", "WEATHER_PROVIDER"):
        environment.setenv(variable, "fake")

    providers = build_providers(load_env())

    assert isinstance(providers.routes, FakeRouteProvider)
    assert isinstance(providers.geocoder, FakeGeocoder)
    assert len(providers.attributions) == 1


def test_limits_come_from_settings(environment: pytest.MonkeyPatch) -> None:
    environment.setenv("WEATHER_MAX_CELLS_PER_TRIP", "120")

    limits = build_limits(load_env())

    assert limits.weather_max_cells == 120
    assert limits.trip_max_distance_km == 3000
