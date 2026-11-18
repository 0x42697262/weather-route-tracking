"""Open-Meteo hourly forecasts (`WeatherProvider`), batched, concurrent and quota-aware.

Each location costs one call against a per-minute quota (`docs/facts.md` F-30, F-48). The
adapter reads `X-RateLimit-Remaining` and `X-RateLimit-Reset` (unix seconds) from every answer;
when the next batch would exceed the remaining calls it waits for the reset if that fits in
`RATE_LIMIT_WAIT_BUDGET_S`, and otherwise skips the batch. Skipped and failed batches leave
their cells out of the result; partial failure never raises.
"""

import asyncio
import json
import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus

import httpx

from core.env import AppEnv
from core.provider_names import WeatherProviderName
from planning.adapters.events import (
    WEATHER_BATCH_FAILED,
    WEATHER_RATE_LIMIT_SKIPPED,
    WEATHER_RATE_LIMIT_WAIT,
)
from planning.adapters.http import Clock, Retrier, build_http_client
from planning.adapters.open_meteo.constants import (
    BATCH_SIZE,
    CELL_SIZE_DEG,
    FORECAST_HORIZON_HOURS,
    RATE_LIMIT_WAIT_BUDGET_S,
)
from planning.adapters.open_meteo.keys import (
    FORECAST_PATH,
    HEADER_RATE_LIMIT_REMAINING,
    HEADER_RATE_LIMIT_RESET,
    OPERATION_FORECAST,
)
from planning.adapters.open_meteo.protocol import forecast_query, parse_forecasts
from planning.domain.values import CellForecast, Coordinate
from planning.errors import UpstreamBusy, UpstreamInvalidResponse, UpstreamUnavailable
from shared.weather_variables import WeatherVariable

logger = logging.getLogger(__name__)

UPSTREAM_ERRORS = (UpstreamBusy, UpstreamInvalidResponse, UpstreamUnavailable)


@dataclass(frozen=True, slots=True)
class _Call:
    """The bounds of one `forecasts` call: its semaphore, wait deadline and wall-clock offset."""

    semaphore: asyncio.Semaphore
    deadline_s: float
    wall_offset_s: float


def _header_float(headers: httpx.Headers, name: str) -> float | None:
    value = headers.get(name)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


class OpenMeteoWeatherProvider:
    """Hourly forecasts per grid cell from Open-Meteo (`WeatherProvider`)."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: str | None,
        retrier: Retrier,
        concurrency: int,
        clock: Clock = time.monotonic,
    ) -> None:
        """Use `client` (base URL and timeouts set); at most `concurrency` calls in flight.

        Waits for a quota reset use the retrier's `sleep`; `clock` is monotonic seconds.
        """
        self._client = client
        self._api_key = api_key
        self._retrier = retrier
        self._concurrency = concurrency
        self._clock = clock
        self._remaining_calls: float | None = None
        self._reset_epoch_s: float | None = None

    @property
    def cell_size_deg(self) -> float:
        """Grid step used to round positions to cells."""
        return CELL_SIZE_DEG

    @property
    def forecast_horizon_hours(self) -> int:
        """Hours from the current hour that every fetched cell covers."""
        return FORECAST_HORIZON_HOURS

    async def forecasts(
        self,
        cells: Sequence[Coordinate],
        variables: frozenset[WeatherVariable],
        now_utc: datetime,
    ) -> Mapping[Coordinate, CellForecast]:
        """Forecasts keyed by the requested cell; cells that failed or were skipped are absent."""
        unique_cells = list(dict.fromkeys(cells))
        if not unique_cells or not variables:
            return {}
        started_s = self._clock()
        call = _Call(
            semaphore=asyncio.Semaphore(self._concurrency),
            deadline_s=started_s + RATE_LIMIT_WAIT_BUDGET_S,
            wall_offset_s=now_utc.timestamp() - started_s,
        )
        batches = [
            unique_cells[start : start + BATCH_SIZE]
            for start in range(0, len(unique_cells), BATCH_SIZE)
        ]
        results = await asyncio.gather(
            *(self._fetch_batch(batch, variables, call) for batch in batches)
        )
        merged: dict[Coordinate, CellForecast] = {}
        for result in results:
            merged.update(result)
        return merged

    async def _fetch_batch(
        self, batch: list[Coordinate], variables: frozenset[WeatherVariable], call: _Call
    ) -> dict[Coordinate, CellForecast]:
        async with call.semaphore:
            if not await self._reserve(len(batch), call):
                return {}
            params = forecast_query(batch, variables, self._api_key)
            try:
                response = await self._retrier.send(
                    OPERATION_FORECAST, lambda: self._client.get(FORECAST_PATH, params=params)
                )
                self._update_quota(response.headers)
                if response.status_code != HTTPStatus.OK:
                    raise UpstreamUnavailable
                forecasts = parse_forecasts(_json(response), batch, variables)
            except UPSTREAM_ERRORS as error:
                logger.warning(
                    WEATHER_BATCH_FAILED,
                    extra={"cells": len(batch), "error": error.code.value},
                )
                return {}
        return {forecast.cell: forecast for forecast in forecasts}

    async def _reserve(self, calls: int, call: _Call) -> bool:
        remaining = self._remaining_calls
        if remaining is None or remaining >= calls:
            if remaining is not None:
                self._remaining_calls = remaining - calls
            return True
        reset_epoch_s = self._reset_epoch_s
        now_s = self._clock()
        wait_s = 0.0 if reset_epoch_s is None else reset_epoch_s - (now_s + call.wall_offset_s)
        if reset_epoch_s is None or now_s + wait_s > call.deadline_s:
            logger.warning(
                WEATHER_RATE_LIMIT_SKIPPED,
                extra={"cells": calls, "remaining_calls": remaining, "wait_s": round(wait_s, 3)},
            )
            return False
        if wait_s > 0:
            logger.info(WEATHER_RATE_LIMIT_WAIT, extra={"wait_s": round(wait_s, 3)})
            await self._retrier.sleep(wait_s)
        self._remaining_calls = None
        return True

    def _update_quota(self, headers: httpx.Headers) -> None:
        remaining = _header_float(headers, HEADER_RATE_LIMIT_REMAINING)
        reset_epoch_s = _header_float(headers, HEADER_RATE_LIMIT_RESET)
        if remaining is not None:
            self._remaining_calls = remaining
        if reset_epoch_s is not None:
            self._reset_epoch_s = reset_epoch_s

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


def _json(response: httpx.Response) -> object:
    try:
        payload: object = response.json()
    except json.JSONDecodeError, UnicodeDecodeError:
        raise UpstreamInvalidResponse from None
    return payload


def build_open_meteo_weather_provider(
    env: AppEnv, transport: httpx.AsyncBaseTransport | None = None
) -> OpenMeteoWeatherProvider:
    """The weather adapter from settings: base URL, optional key, timeouts and concurrency."""
    api_key = env.open_meteo_api_key.get_secret_value() if env.open_meteo_api_key else None
    client = build_http_client(
        str(env.open_meteo_base_url),
        env.http_connect_timeout_seconds,
        env.http_read_timeout_seconds,
        transport,
    )
    return OpenMeteoWeatherProvider(
        client,
        api_key,
        Retrier(provider=WeatherProviderName.OPEN_METEO.value),
        env.outbound_concurrency,
    )
