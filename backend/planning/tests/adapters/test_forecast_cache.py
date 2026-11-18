import logging
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.core.cache.backends.locmem import LocMemCache

from planning.adapters.forecast_cache import (
    FORECAST_CACHE_SCHEMA_VERSION,
    CachingWeatherProvider,
    decode_forecast,
    encode_forecast,
)
from planning.adapters.keys import forecast_cache_key
from planning.domain.values import CellForecast, Coordinate
from shared.weather_variables import WeatherVariable

NOW = datetime(2026, 11, 17, 6, 0, tzinfo=UTC)
TTL_S = 1800
DALLAS = Coordinate(latitude=32.8, longitude=-96.8)
DENTON = Coordinate(latitude=33.2, longitude=-97.1)
WIND = frozenset({WeatherVariable.WIND_SPEED})
WIND_AND_RAIN = frozenset({WeatherVariable.WIND_SPEED, WeatherVariable.RAIN_RATE})


def _forecast(cell: Coordinate, variables: frozenset[WeatherVariable]) -> CellForecast:
    hours = tuple(NOW + timedelta(hours=index) for index in range(3))
    return CellForecast(
        cell=cell,
        hours_utc=hours,
        values=dict.fromkeys(variables, (1.5, None, cell.latitude)),
    )


class FakeWeather:
    """An in-memory weather provider that records what it was asked for."""

    cell_size_deg = 0.1
    forecast_horizon_hours = 144

    def __init__(self, failing: frozenset[Coordinate] = frozenset()) -> None:
        self.calls: list[list[Coordinate]] = []
        self.failing = failing

    async def forecasts(
        self,
        cells: Sequence[Coordinate],
        variables: frozenset[WeatherVariable],
        now_utc: datetime,
    ) -> Mapping[Coordinate, CellForecast]:
        self.calls.append(list(cells))
        assert now_utc == NOW
        return {cell: _forecast(cell, variables) for cell in cells if cell not in self.failing}


@pytest.fixture
def cache() -> LocMemCache:
    return LocMemCache(f"forecast-test-{uuid.uuid4()}", {})


async def test_second_request_is_served_from_the_cache(cache: LocMemCache) -> None:
    inner = FakeWeather()
    provider = CachingWeatherProvider(inner, cache, TTL_S)

    first = await provider.forecasts([DALLAS, DENTON, DALLAS], WIND, NOW)
    second = await provider.forecasts([DENTON, DALLAS], WIND, NOW)

    assert inner.calls == [[DALLAS, DENTON]]
    assert first == second
    assert second[DALLAS] == _forecast(DALLAS, WIND)


async def test_only_misses_are_fetched(cache: LocMemCache) -> None:
    inner = FakeWeather()
    provider = CachingWeatherProvider(inner, cache, TTL_S)
    await provider.forecasts([DALLAS], WIND, NOW)

    result = await provider.forecasts([DALLAS, DENTON], WIND, NOW)

    assert inner.calls == [[DALLAS], [DENTON]]
    assert set(result) == {DALLAS, DENTON}


async def test_another_variable_set_is_a_miss(cache: LocMemCache) -> None:
    inner = FakeWeather()
    provider = CachingWeatherProvider(inner, cache, TTL_S)
    await provider.forecasts([DALLAS], WIND, NOW)

    result = await provider.forecasts([DALLAS], WIND_AND_RAIN, NOW)

    assert inner.calls == [[DALLAS], [DALLAS]]
    assert set(result[DALLAS].values) == WIND_AND_RAIN


async def test_another_schema_version_is_a_miss(cache: LocMemCache) -> None:
    inner = FakeWeather()
    key = forecast_cache_key(FORECAST_CACHE_SCHEMA_VERSION, DALLAS, WIND)
    stale = encode_forecast(_forecast(DALLAS, WIND)) | {"schema_version": 99}
    await cache.aset(key, stale)

    await CachingWeatherProvider(inner, cache, TTL_S).forecasts([DALLAS], WIND, NOW)

    assert inner.calls == [[DALLAS]]
    assert await cache.aget(key) == encode_forecast(_forecast(DALLAS, WIND))


@pytest.mark.parametrize(
    "payload",
    [
        "not a forecast",
        {"schema_version": FORECAST_CACHE_SCHEMA_VERSION},
        {
            "schema_version": FORECAST_CACHE_SCHEMA_VERSION,
            "hours_utc_s": [1, 2],
            "values": {"wind_speed": [1.0]},
        },
        {
            "schema_version": FORECAST_CACHE_SCHEMA_VERSION,
            "hours_utc_s": [1],
            "values": {"rain_rate": [1.0]},
        },
        {
            "schema_version": FORECAST_CACHE_SCHEMA_VERSION,
            "hours_utc_s": [1],
            "values": {"wind_speed": [1.0]},
            "extra": True,
        },
    ],
    ids=["text", "no-fields", "length-mismatch", "other-variables", "unknown-field"],
)
def test_malformed_payloads_are_misses(payload: object) -> None:
    assert decode_forecast(payload, DALLAS, WIND) is None


def test_payload_round_trips() -> None:
    forecast = _forecast(DALLAS, WIND_AND_RAIN)

    assert decode_forecast(encode_forecast(forecast), DALLAS, WIND_AND_RAIN) == forecast


async def test_failed_cells_are_absent_not_cached_and_logged(
    cache: LocMemCache, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    inner = FakeWeather(failing=frozenset({DENTON}))
    provider = CachingWeatherProvider(inner, cache, TTL_S)
    await provider.forecasts([DALLAS], WIND, NOW)

    result = await provider.forecasts([DALLAS, DENTON], WIND, NOW)

    assert set(result) == {DALLAS}
    assert await cache.aget(forecast_cache_key(FORECAST_CACHE_SCHEMA_VERSION, DENTON, WIND)) is None
    fetched = [record for record in caplog.records if record.getMessage() == "weather.fetched"]
    last = fetched[-1].__dict__
    assert (last["cells_requested"], last["cache_hits"], last["cache_misses"]) == (2, 1, 1)
    assert last["failures"] == 1


class TimeoutRecordingCache(LocMemCache):
    """A local-memory cache that records the timeout of every `set_many`."""

    def __init__(self) -> None:
        super().__init__(f"forecast-test-{uuid.uuid4()}", {})
        self.timeouts: list[float | None] = []

    def set_many(
        self, data: dict[str, Any], timeout: float | None = None, version: int | None = None
    ) -> list[str]:
        self.timeouts.append(timeout)
        return super().set_many(data, timeout, version)


async def test_entries_are_written_with_the_ttl() -> None:
    cache = TimeoutRecordingCache()

    await CachingWeatherProvider(FakeWeather(), cache, TTL_S).forecasts([DALLAS], WIND, NOW)

    assert cache.timeouts == [TTL_S]


async def test_no_cells_ask_nothing(cache: LocMemCache) -> None:
    inner = FakeWeather()

    assert await CachingWeatherProvider(inner, cache, TTL_S).forecasts([], WIND, NOW) == {}
    assert inner.calls == []


def test_grid_properties_come_from_the_inner_provider(cache: LocMemCache) -> None:
    provider = CachingWeatherProvider(FakeWeather(), cache, TTL_S)

    assert provider.cell_size_deg == 0.1
    assert provider.forecast_horizon_hours == 144


def test_cache_key_names_version_cell_and_variables() -> None:
    assert forecast_cache_key(1, DALLAS, WIND_AND_RAIN) == (
        "forecast:v1:32.8000,-96.8000:rain_rate+wind_speed"
    )
