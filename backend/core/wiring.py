"""The composition root: the one place that builds providers and bounds from settings.

Providers are picked by name from one table per kind, built lazily once per process, and the
weather provider is wrapped in the forecast cache. Tests swap the whole set with
`use_providers`.
"""

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from types import MappingProxyType

from django.conf import settings
from django.core.cache import cache

from core.env import AppEnv
from core.provider_names import GeocoderName, RouteProviderName, WeatherProviderName
from planning.adapters.fake.places import build_fake_geocoder
from planning.adapters.fake.routes import build_fake_route_provider
from planning.adapters.fake.weather import build_fake_weather_provider
from planning.adapters.forecast_cache import CachingWeatherProvider
from planning.adapters.open_meteo.client import build_open_meteo_weather_provider
from planning.adapters.tomtom.client import build_tomtom_geocoder, build_tomtom_route_provider
from planning.domain.providers import Geocoder, RouteProvider, WeatherProvider
from planning.keys import OPEN_METEO_ATTRIBUTION_URL
from planning.services.attribution import Attribution
from planning.services.limits import PlanningLimits
from planning.text import (
    FAKE_DATA_ATTRIBUTION,
    OPEN_METEO_ATTRIBUTION,
    TOMTOM_PLACES_ATTRIBUTION,
    TOMTOM_ROUTING_ATTRIBUTION,
)


@dataclass(frozen=True, slots=True)
class ProviderEntry[ProviderT]:
    """How to build one adapter from settings, and the notice its data needs."""

    build: Callable[[AppEnv], ProviderT]
    attribution: Attribution


FAKE_ATTRIBUTION = Attribution(text=FAKE_DATA_ATTRIBUTION, url=None)

ROUTE_PROVIDERS: Mapping[RouteProviderName, ProviderEntry[RouteProvider]] = MappingProxyType(
    {
        RouteProviderName.TOMTOM: ProviderEntry(
            build_tomtom_route_provider, Attribution(text=TOMTOM_ROUTING_ATTRIBUTION, url=None)
        ),
        RouteProviderName.FAKE: ProviderEntry(
            lambda _env: build_fake_route_provider(), FAKE_ATTRIBUTION
        ),
    },
)
GEOCODERS: Mapping[GeocoderName, ProviderEntry[Geocoder]] = MappingProxyType(
    {
        GeocoderName.TOMTOM: ProviderEntry(
            build_tomtom_geocoder, Attribution(text=TOMTOM_PLACES_ATTRIBUTION, url=None)
        ),
        GeocoderName.FAKE: ProviderEntry(lambda _env: build_fake_geocoder(), FAKE_ATTRIBUTION),
    },
)
WEATHER_PROVIDERS: Mapping[WeatherProviderName, ProviderEntry[WeatherProvider]] = MappingProxyType(
    {
        WeatherProviderName.OPEN_METEO: ProviderEntry(
            build_open_meteo_weather_provider,
            Attribution(text=OPEN_METEO_ATTRIBUTION, url=OPEN_METEO_ATTRIBUTION_URL),
        ),
        WeatherProviderName.FAKE: ProviderEntry(
            lambda _env: build_fake_weather_provider(), FAKE_ATTRIBUTION
        ),
    },
)


@dataclass(frozen=True, slots=True)
class Providers:
    """The adapters a request uses, the name of the routing one, and the notices to show."""

    routes: RouteProvider
    route_provider_name: str
    geocoder: Geocoder
    weather: WeatherProvider
    attributions: tuple[Attribution, ...]


def build_providers(env: AppEnv) -> Providers:
    """Build the chosen adapters; weather goes through the forecast cache."""
    route_entry = ROUTE_PROVIDERS[env.route_provider]
    geocoder_entry = GEOCODERS[env.geocoder]
    weather_entry = WEATHER_PROVIDERS[env.weather_provider]
    notices = (route_entry.attribution, geocoder_entry.attribution, weather_entry.attribution)
    return Providers(
        routes=route_entry.build(env),
        route_provider_name=env.route_provider.value,
        geocoder=geocoder_entry.build(env),
        weather=CachingWeatherProvider(
            weather_entry.build(env), cache, env.forecast_cache_ttl_seconds
        ),
        attributions=tuple(dict.fromkeys(notices)),
    )


def build_limits(env: AppEnv) -> PlanningLimits:
    """The planning bounds from settings."""
    return PlanningLimits(
        trip_max_distance_km=env.trip_max_distance_km,
        max_checkpoints_per_route=env.trip_max_checkpoints_per_route,
        route_alternatives_requested=env.route_alternatives_requested,
        route_max_extra_requests=env.route_max_extra_requests,
        weather_max_cells=env.weather_max_cells_per_trip,
    )


class _Built:
    current: Providers | None = None


def providers() -> Providers:
    """The process's providers, built on first use."""
    if _Built.current is None:
        _Built.current = build_providers(settings.APP_ENV)
    return _Built.current


def limits() -> PlanningLimits:
    """The planning bounds from settings."""
    return build_limits(settings.APP_ENV)


@contextmanager
def use_providers(replacement: Providers) -> Iterator[Providers]:
    """Serve `replacement` until the block ends (tests)."""
    previous = _Built.current
    _Built.current = replacement
    try:
        yield replacement
    finally:
        _Built.current = previous
