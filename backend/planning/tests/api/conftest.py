from collections.abc import Iterator

import pytest
from django.core.cache import cache
from django.core.cache.backends.locmem import LocMemCache

from core.wiring import FAKE_ATTRIBUTION, Providers, use_providers
from planning.adapters.fake.places import FakeGeocoder
from planning.adapters.fake.routes import FakeRouteProvider
from planning.adapters.fake.weather import FakeWeatherProvider
from planning.adapters.forecast_cache import CachingWeatherProvider
from planning.domain.providers import Geocoder, RouteProvider

FORECAST_TTL_S = 600


def fake_providers(
    routes: RouteProvider | None = None, geocoder: Geocoder | None = None
) -> Providers:
    """The fake providers, with routing or place search optionally replaced."""
    return Providers(
        routes=routes or FakeRouteProvider(),
        route_provider_name="fake",
        geocoder=geocoder or FakeGeocoder(),
        weather=CachingWeatherProvider(
            FakeWeatherProvider(), LocMemCache("api-tests", {}), FORECAST_TTL_S
        ),
        attributions=(FAKE_ATTRIBUTION,),
    )


@pytest.fixture(autouse=True)
def fakes() -> Iterator[Providers]:
    """Every API test runs on the fake providers with an empty cache."""
    cache.clear()
    with use_providers(fake_providers()) as providers:
        yield providers
