"""A deterministic, keyless `WeatherProvider`: smooth waves of wind, rain and snow that drift
with time, so any trip meets several levels, including narrow No Travel bands."""

import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta

from planning.adapters.fake.constants import (
    CELL_SIZE_DEG,
    FORECAST_HORIZON_HOURS,
    HOURS_PER_DAY,
    RAIN_LATITUDE_RAD_PER_DEG,
    RAIN_LONGITUDE_RAD_PER_DEG,
    RAIN_RAD_PER_HOUR,
    RAIN_SHARPNESS,
    RAIN_SWING_MM_PER_H,
    SNOW_FROM_LATITUDE_DEG,
    SNOW_LONGITUDE_RAD_PER_DEG,
    SNOW_RAD_PER_HOUR,
    SNOW_SWING_CM_PER_H,
    VALUE_DECIMALS,
    WIND_BASE_KMH,
    WIND_LATITUDE_RAD_PER_DEG,
    WIND_LONGITUDE_RAD_PER_DEG,
    WIND_RAD_PER_HOUR,
    WIND_SHARPNESS,
    WIND_SWING_KMH,
)
from planning.constants import SECONDS_PER_HOUR
from planning.domain.values import CellForecast, Coordinate
from shared.weather_variables import WeatherVariable

ONE_HOUR = timedelta(hours=1)


def _hours_since_epoch(moment: datetime) -> float:
    return moment.timestamp() / SECONDS_PER_HOUR


def wind_speed_kmh(cell: Coordinate, hour: float) -> float:
    """Wind at a cell and hour since the epoch: isolated storms on a drifting checkerboard."""
    wave = math.sin(cell.latitude * WIND_LATITUDE_RAD_PER_DEG + hour * WIND_RAD_PER_HOUR) * (
        math.sin(cell.longitude * WIND_LONGITUDE_RAD_PER_DEG - hour * WIND_RAD_PER_HOUR)
    )
    return WIND_BASE_KMH + WIND_SWING_KMH * max(0.0, wave) ** WIND_SHARPNESS


def rain_rate_mm_per_h(cell: Coordinate, hour: float) -> float:
    """Rain at a cell and hour since the epoch."""
    wave = math.cos(
        cell.latitude * RAIN_LATITUDE_RAD_PER_DEG
        - cell.longitude * RAIN_LONGITUDE_RAD_PER_DEG
        + hour * RAIN_RAD_PER_HOUR
    )
    return RAIN_SWING_MM_PER_H * max(0.0, wave) ** RAIN_SHARPNESS


def snowfall_rate_cm_per_h(cell: Coordinate, hour: float) -> float:
    """Snow at a cell and hour since the epoch; none south of `SNOW_FROM_LATITUDE_DEG`."""
    if cell.latitude < SNOW_FROM_LATITUDE_DEG:
        return 0.0
    wave = math.sin(cell.longitude * SNOW_LONGITUDE_RAD_PER_DEG + hour * SNOW_RAD_PER_HOUR)
    return SNOW_SWING_CM_PER_H * max(0.0, wave)


PATTERNS = {
    WeatherVariable.WIND_SPEED: wind_speed_kmh,
    WeatherVariable.RAIN_RATE: rain_rate_mm_per_h,
    WeatherVariable.SNOWFALL_RATE: snowfall_rate_cm_per_h,
}


def _forecast(
    cell: Coordinate, variables: frozenset[WeatherVariable], hours_utc: tuple[datetime, ...]
) -> CellForecast:
    hours = [_hours_since_epoch(moment) for moment in hours_utc]
    return CellForecast(
        cell=cell,
        hours_utc=hours_utc,
        values={
            variable: tuple(round(PATTERNS[variable](cell, hour), VALUE_DECIMALS) for hour in hours)
            for variable in variables
        },
    )


class FakeWeatherProvider:
    """Patterned hourly forecasts (`WeatherProvider`); never calls anything."""

    @property
    def cell_size_deg(self) -> float:
        """Same grid step as the Open-Meteo adapter."""
        return CELL_SIZE_DEG

    @property
    def forecast_horizon_hours(self) -> int:
        """Same horizon as the Open-Meteo adapter."""
        return FORECAST_HORIZON_HOURS

    async def forecasts(
        self,
        cells: Sequence[Coordinate],
        variables: frozenset[WeatherVariable],
        now_utc: datetime,
    ) -> Mapping[Coordinate, CellForecast]:
        """Every requested cell, from 00:00 UTC today to the horizon."""
        start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        hours_utc = tuple(
            start + ONE_HOUR * hour for hour in range(FORECAST_HORIZON_HOURS + HOURS_PER_DAY)
        )
        return {cell: _forecast(cell, variables, hours_utc) for cell in dict.fromkeys(cells)}

    async def aclose(self) -> None:
        """Nothing to close."""


def build_fake_weather_provider() -> FakeWeatherProvider:
    """The fake weather adapter."""
    return FakeWeatherProvider()
