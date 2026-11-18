"""A `WeatherProvider` that reads forecast cells from the Django cache before asking another.

Only weather cells are cached; nothing from TomTom ever is (`docs/facts.md` F-52). Payloads
carry `schema_version`; an unknown version or malformed payload is a miss.
"""

import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from django.core.cache.backends.base import BaseCache
from pydantic import BaseModel, ConfigDict, ValidationError

from planning.adapters.events import WEATHER_FETCHED
from planning.adapters.keys import forecast_cache_key
from planning.domain.providers import WeatherProvider
from planning.domain.values import CellForecast, Coordinate
from shared.weather_variables import WeatherVariable

logger = logging.getLogger(__name__)

FORECAST_CACHE_SCHEMA_VERSION = 1
DUMP_MODE_JSON = "json"


class _CachedForecast(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int
    hours_utc_s: tuple[int, ...]
    values: dict[WeatherVariable, tuple[float | None, ...]]


def encode_forecast(forecast: CellForecast) -> dict[str, object]:
    """The cache payload of one cell's forecast."""
    return _CachedForecast(
        schema_version=FORECAST_CACHE_SCHEMA_VERSION,
        hours_utc_s=tuple(int(hour.timestamp()) for hour in forecast.hours_utc),
        values=dict(forecast.values),
    ).model_dump(mode=DUMP_MODE_JSON)


def decode_forecast(
    payload: object, cell: Coordinate, variables: frozenset[WeatherVariable]
) -> CellForecast | None:
    """The forecast in a cache payload, or None when it is missing, malformed or another version."""
    if payload is None:
        return None
    try:
        cached = _CachedForecast.model_validate(payload)
    except ValidationError:
        return None
    hour_count = len(cached.hours_utc_s)
    is_current = cached.schema_version == FORECAST_CACHE_SCHEMA_VERSION
    has_variables = set(cached.values) == set(variables)
    lengths_match = all(len(series) == hour_count for series in cached.values.values())
    if not (is_current and has_variables and lengths_match):
        return None
    return CellForecast(
        cell=cell,
        hours_utc=tuple(datetime.fromtimestamp(second, UTC) for second in cached.hours_utc_s),
        values=dict(cached.values),
    )


class CachingWeatherProvider:
    """Serves cached cells and fetches only the misses from `inner` (`WeatherProvider`)."""

    def __init__(self, inner: WeatherProvider, cache: BaseCache, ttl_s: int) -> None:
        """Wrap `inner`; fetched cells stay in `cache` for `ttl_s` seconds."""
        self._inner = inner
        self._cache = cache
        self._ttl_s = ttl_s

    @property
    def cell_size_deg(self) -> float:
        """The inner provider's grid step."""
        return self._inner.cell_size_deg

    @property
    def forecast_horizon_hours(self) -> int:
        """The inner provider's horizon."""
        return self._inner.forecast_horizon_hours

    async def forecasts(
        self,
        cells: Sequence[Coordinate],
        variables: frozenset[WeatherVariable],
        now_utc: datetime,
    ) -> Mapping[Coordinate, CellForecast]:
        """Forecasts keyed by the requested cell; cells that failed are absent."""
        keys = {
            cell: forecast_cache_key(FORECAST_CACHE_SCHEMA_VERSION, cell, variables)
            for cell in dict.fromkeys(cells)
        }
        if not keys:
            return {}
        cached = await self._cache.aget_many(list(keys.values()))
        found: dict[Coordinate, CellForecast] = {}
        for cell, key in keys.items():
            forecast = decode_forecast(cached.get(key), cell, variables)
            if forecast is not None:
                found[cell] = forecast
        misses = [cell for cell in keys if cell not in found]
        answered = await self._inner.forecasts(misses, variables, now_utc) if misses else {}
        fetched = {cell: answered[cell] for cell in misses if cell in answered}
        if fetched:
            await self._cache.aset_many(
                {keys[cell]: encode_forecast(forecast) for cell, forecast in fetched.items()},
                timeout=self._ttl_s,
            )
        logger.info(
            WEATHER_FETCHED,
            extra={
                "cells_requested": len(keys),
                "cache_hits": len(found),
                "cache_misses": len(misses),
                "failures": len(misses) - len(fetched),
            },
        )
        return found | fetched
