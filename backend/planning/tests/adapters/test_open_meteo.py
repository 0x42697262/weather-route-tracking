import asyncio
import copy
import logging
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from django.conf import settings

from planning.adapters.open_meteo.client import (
    OpenMeteoWeatherProvider,
    build_open_meteo_weather_provider,
)
from planning.adapters.open_meteo.protocol import forecast_query, parse_forecasts
from planning.domain.values import Coordinate
from planning.errors import UpstreamInvalidResponse
from planning.tests.adapters.support import FakeTime, fixture_json, make_retrier
from shared.weather_variables import WeatherVariable

BASE_URL = "https://weather.example.com"
OKLAHOMA_CITY = Coordinate(latitude=35.477, longitude=-97.5064)
NOME = Coordinate(latitude=64.5011, longitude=-165.4064)
KHOVD = Coordinate(latitude=48.0056, longitude=91.6419)
THREE_CELLS = (OKLAHOMA_CITY, NOME, KHOVD)
ALL_VARIABLES = frozenset(WeatherVariable)
NOW = datetime(2026, 11, 17, 5, 40, tzinfo=UTC)
FIRST_HOUR = datetime(2026, 11, 17, 0, 0, tzinfo=UTC)

type Handler = Callable[[httpx.Request], httpx.Response]


def _three_cells() -> list[dict[str, Any]]:
    payload = copy.deepcopy(fixture_json("open_meteo_three_cells.json"))
    assert isinstance(payload, list)
    return payload


def _locations_in(request: httpx.Request) -> int:
    return len(request.url.params["latitude"].split(","))


def _answer_every_location(
    headers: dict[str, str] | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    template = _three_cells()[0]

    def answer(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[template] * _locations_in(request), headers=headers or {})

    return answer


def _cells(count: int) -> list[Coordinate]:
    return [Coordinate(latitude=10.0 + index / 10, longitude=20.0) for index in range(count)]


@pytest.fixture
def fake_time() -> FakeTime:
    return FakeTime()


@pytest.fixture
async def make_provider(
    fake_time: FakeTime,
) -> AsyncIterator[Callable[..., OpenMeteoWeatherProvider]]:
    clients: list[httpx.AsyncClient] = []

    def build(
        handler: Callable[[httpx.Request], Any],
        concurrency: int = 8,
        api_key: str | None = None,
    ) -> OpenMeteoWeatherProvider:
        client = httpx.AsyncClient(base_url=BASE_URL, transport=httpx.MockTransport(handler))
        clients.append(client)
        return OpenMeteoWeatherProvider(
            client, api_key, make_retrier(fake_time), concurrency, clock=fake_time.clock
        )

    yield build
    for client in clients:
        await client.aclose()


def test_query_asks_only_for_the_needed_fields() -> None:
    query = dict(forecast_query(THREE_CELLS, ALL_VARIABLES, None))

    assert query == {
        "latitude": "35.4770,64.5011,48.0056",
        "longitude": "-97.5064,-165.4064,91.6419",
        "hourly": "rain,showers,snowfall,wind_speed_10m",
        "forecast_days": "7",
        "timeformat": "unixtime",
        "timezone": "GMT",
    }
    wind_only = dict(forecast_query(THREE_CELLS, frozenset({WeatherVariable.WIND_SPEED}), None))
    assert wind_only["hourly"] == "wind_speed_10m"


def test_query_sends_the_key_only_when_set() -> None:
    assert ("apikey", "paid") in forecast_query(THREE_CELLS, ALL_VARIABLES, "paid")
    assert "apikey" not in dict(forecast_query(THREE_CELLS, ALL_VARIABLES, ""))


def test_recorded_response_is_parsed_per_requested_cell_in_metric() -> None:
    forecasts = parse_forecasts(_three_cells(), THREE_CELLS, ALL_VARIABLES)

    oklahoma_city, nome, khovd = forecasts
    assert (oklahoma_city.cell, nome.cell, khovd.cell) == THREE_CELLS
    assert len(oklahoma_city.hours_utc) == 168
    assert oklahoma_city.hours_utc[0] == FIRST_HOUR
    assert oklahoma_city.hours_utc[-1] == datetime(2026, 11, 23, 23, 0, tzinfo=UTC)
    assert oklahoma_city.values[WeatherVariable.WIND_SPEED][:3] == (2.3, 6.7, 7.0)
    assert oklahoma_city.values[WeatherVariable.RAIN_RATE][163] == pytest.approx(0.2)
    assert nome.values[WeatherVariable.RAIN_RATE][39] == pytest.approx(0.1)
    assert nome.values[WeatherVariable.RAIN_RATE][46] == pytest.approx(0.1)
    assert nome.values[WeatherVariable.SNOWFALL_RATE][38:40] == (0.28, 0.84)
    assert set(khovd.values) == ALL_VARIABLES


def test_a_single_location_answer_is_an_object() -> None:
    payload = fixture_json("open_meteo_one_cell_wind.json")

    (forecast,) = parse_forecasts(
        payload, (OKLAHOMA_CITY,), frozenset({WeatherVariable.WIND_SPEED})
    )

    assert forecast.values[WeatherVariable.WIND_SPEED][:2] == (2.3, 6.7)


def test_a_missing_component_makes_the_sum_missing() -> None:
    payload = _three_cells()
    payload[0]["hourly"]["showers"][163] = None

    forecasts = parse_forecasts(payload, THREE_CELLS, ALL_VARIABLES)

    assert forecasts[0].values[WeatherVariable.RAIN_RATE][163] is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload.pop(),
        lambda payload: payload[0]["hourly_units"].update(wind_speed_10m="mp/h"),
        lambda payload: payload[0]["hourly"].pop("snowfall"),
        lambda payload: payload[0]["hourly"]["rain"].pop(),
        lambda payload: payload[0]["hourly"]["time"].__setitem__(1, 1794873601),
        lambda payload: payload[0]["hourly"]["time"].__setitem__(2, 1794873600),
        lambda payload: payload[0]["hourly"]["wind_speed_10m"].__setitem__(0, "fast"),
        lambda payload: payload[0]["hourly_units"].update(time="iso8601"),
    ],
    ids=[
        "fewer-locations",
        "unexpected-unit",
        "missing-field",
        "short-series",
        "time-off-the-hour",
        "time-not-consecutive",
        "not-a-number",
        "not-unix-time",
    ],
)
def test_malformed_responses_are_rejected(mutate: Callable[[list[Any]], object]) -> None:
    payload = _three_cells()
    mutate(payload)

    with pytest.raises(UpstreamInvalidResponse):
        parse_forecasts(payload, THREE_CELLS, ALL_VARIABLES)


async def test_forecasts_are_keyed_by_the_requested_cell(
    make_provider: Callable[..., OpenMeteoWeatherProvider],
) -> None:
    requests: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_three_cells())

    provider = make_provider(answer)

    forecasts = await provider.forecasts([*THREE_CELLS, NOME], ALL_VARIABLES, NOW)

    assert list(forecasts) == list(THREE_CELLS)
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == "/v1/forecast"
    assert provider.cell_size_deg == 0.1
    assert provider.forecast_horizon_hours == 144


async def test_cells_are_batched(make_provider: Callable[..., OpenMeteoWeatherProvider]) -> None:
    sizes: list[int] = []
    answer_all = _answer_every_location()

    def answer(request: httpx.Request) -> httpx.Response:
        sizes.append(_locations_in(request))
        return answer_all(request)

    forecasts = await make_provider(answer).forecasts(_cells(120), ALL_VARIABLES, NOW)

    assert sorted(sizes) == [20, 50, 50]
    assert len(forecasts) == 120


async def test_concurrency_is_bounded(
    make_provider: Callable[..., OpenMeteoWeatherProvider],
) -> None:
    in_flight = 0
    most_in_flight = 0
    answer_all = _answer_every_location()

    async def answer(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight, most_in_flight
        in_flight += 1
        most_in_flight = max(most_in_flight, in_flight)
        await asyncio.sleep(0)
        in_flight -= 1
        return answer_all(request)

    forecasts = await make_provider(answer, concurrency=2).forecasts(
        _cells(250), ALL_VARIABLES, NOW
    )

    assert len(forecasts) == 250
    assert most_in_flight == 2


async def test_a_failed_batch_leaves_its_cells_out(
    make_provider: Callable[..., OpenMeteoWeatherProvider],
    caplog: pytest.LogCaptureFixture,
) -> None:
    cells = _cells(60)
    failing_latitude = f"{cells[0].latitude:.4f}"
    answer_all = _answer_every_location()

    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.params["latitude"].startswith(failing_latitude):
            return httpx.Response(503)
        return answer_all(request)

    forecasts = await make_provider(answer).forecasts(cells, ALL_VARIABLES, NOW)

    assert set(forecasts) == set(cells[50:])
    assert "weather.batch_failed" in caplog.text


async def test_a_malformed_batch_leaves_its_cells_out(
    make_provider: Callable[..., OpenMeteoWeatherProvider],
) -> None:
    forecasts = await make_provider(lambda _: httpx.Response(200, text="nope")).forecasts(
        THREE_CELLS, ALL_VARIABLES, NOW
    )

    assert forecasts == {}


async def test_retry_on_429_then_success(
    make_provider: Callable[..., OpenMeteoWeatherProvider], fake_time: FakeTime
) -> None:
    responses = [httpx.Response(429), httpx.Response(200, json=_three_cells())]

    forecasts = await make_provider(lambda _: responses.pop(0)).forecasts(
        THREE_CELLS, ALL_VARIABLES, NOW
    )

    assert len(forecasts) == 3
    assert fake_time.sleeps == [0.5]


async def test_timeouts_leave_cells_out(
    make_provider: Callable[..., OpenMeteoWeatherProvider],
) -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        msg = "slow"
        raise httpx.ReadTimeout(msg, request=request)

    assert await make_provider(answer).forecasts(THREE_CELLS, ALL_VARIABLES, NOW) == {}


async def test_waits_for_the_quota_reset_within_the_budget(
    make_provider: Callable[..., OpenMeteoWeatherProvider], fake_time: FakeTime
) -> None:
    reset_epoch_s = NOW.timestamp() + 5
    answer = _answer_every_location(
        {"X-RateLimit-Remaining": "10.0", "X-RateLimit-Reset": str(int(reset_epoch_s))}
    )

    forecasts = await make_provider(answer, concurrency=1).forecasts(
        _cells(100), ALL_VARIABLES, NOW
    )

    assert len(forecasts) == 100
    assert fake_time.sleeps == [pytest.approx(5.0)]


async def test_skips_batches_when_the_reset_is_too_far(
    make_provider: Callable[..., OpenMeteoWeatherProvider],
    fake_time: FakeTime,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    reset_epoch_s = NOW.timestamp() + 55
    answer = _answer_every_location(
        {"X-RateLimit-Remaining": "10.0", "X-RateLimit-Reset": str(int(reset_epoch_s))}
    )

    forecasts = await make_provider(answer, concurrency=1).forecasts(
        _cells(100), ALL_VARIABLES, NOW
    )

    assert len(forecasts) == 50
    assert fake_time.sleeps == []
    assert "weather.rate_limit_skipped" in caplog.text


async def test_no_cells_or_no_variables_cost_no_call(
    make_provider: Callable[..., OpenMeteoWeatherProvider],
) -> None:
    requests: list[httpx.Request] = []
    provider = make_provider(requests.append)

    assert await provider.forecasts([], ALL_VARIABLES, NOW) == {}
    assert await provider.forecasts(THREE_CELLS, frozenset(), NOW) == {}
    assert requests == []


async def test_factory_uses_the_base_url_from_settings() -> None:
    requests: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_three_cells())

    provider = build_open_meteo_weather_provider(settings.APP_ENV, httpx.MockTransport(answer))
    try:
        forecasts = await provider.forecasts(THREE_CELLS, ALL_VARIABLES, NOW)
    finally:
        await provider.aclose()

    assert len(forecasts) == 3
    assert requests[0].url.host == settings.APP_ENV.open_meteo_base_url.host
    assert "apikey" not in requests[0].url.params
