from datetime import timedelta

import pytest

from planning.domain.geometry import encode_polyline
from planning.domain.risk_constants import FORECAST_WINDOW_HOURS
from planning.errors import InvalidRequest, PlanningError, Rejection, TripOptionsInvalid
from planning.services.constants import GRID_MAX_POINTS_PER_LINE
from planning.services.weather_grid import GridRequest, WeatherGrid, build_weather_grid
from planning.tests.services.support import (
    CHICAGO,
    DENVER,
    DEPARTURE,
    LIMITS,
    NOW,
    RULE_SET,
    RecordingWeather,
    route,
)
from shared.risk_levels import RiskLevel

LINE = encode_polyline(route().points)


async def grid(request: GridRequest, weather: RecordingWeather) -> WeatherGrid:
    return await build_weather_grid(
        request, weather=weather, rule_set=RULE_SET, limits=LIMITS, now_utc=NOW
    )


async def test_a_normal_grid_covers_every_hour_of_the_window() -> None:
    weather = RecordingWeather()

    result = await grid(GridRequest((LINE,), DEPARTURE, 10000.0), weather)

    assert len(weather.calls) == 1
    assert len(result.grid.cells) == len(weather.calls[0])
    assert len(result.grid.cells) <= LIMITS.weather_max_cells
    assert len(result.grid.hours_utc) == FORECAST_WINDOW_HOURS + 1
    assert result.grid.hours_utc[0] == DEPARTURE
    assert all(level is RiskLevel.LOW for level in result.grid.cells[0].combined)
    assert result.cells_missing == 0


async def test_a_long_trip_grows_the_cells_to_fit_the_cap() -> None:
    weather = RecordingWeather()
    line = encode_polyline(route(CHICAGO, DENVER).points)

    result = await grid(GridRequest((line,), DEPARTURE, 10000.0), weather)

    assert result.cell_size_deg > weather.cell_size_deg
    assert len(result.grid.cells) <= LIMITS.weather_max_cells


async def test_missing_cells_are_unknown() -> None:
    weather = RecordingWeather(fails=lambda _cell: True)

    result = await grid(GridRequest((LINE,), DEPARTURE, 10000.0), weather)

    assert result.cells_missing == len(result.grid.cells)
    assert all(level is None for level in result.grid.cells[0].combined)


TOO_MANY_POINTS = encode_polyline(route(CHICAGO, DENVER).points * 14)


@pytest.mark.parametrize(
    ("request_", "error", "reason"),
    [
        (
            GridRequest(("not a polyline ~~~",), DEPARTURE, 1.0),
            InvalidRequest,
            Rejection.LINE_INVALID,
        ),
        (GridRequest(("_p~iF",), DEPARTURE, 1.0), InvalidRequest, Rejection.LINE_INVALID),
        (
            GridRequest((LINE, TOO_MANY_POINTS), DEPARTURE, 1.0),
            InvalidRequest,
            Rejection.LINE_INVALID,
        ),
        (
            GridRequest((encode_polyline(route(CHICAGO, DENVER).points * 3),), DEPARTURE, 1.0),
            InvalidRequest,
            Rejection.TRIP_TOO_LONG,
        ),
        (
            GridRequest((LINE,), NOW + timedelta(hours=97), 1.0),
            InvalidRequest,
            Rejection.DEPARTURE_OUT_OF_RANGE,
        ),
        (GridRequest((LINE,), DEPARTURE, 90000.0), TripOptionsInvalid, None),
    ],
)
async def test_requests_over_the_caps_call_no_provider(
    request_: GridRequest, error: type[PlanningError], reason: Rejection | None
) -> None:
    weather = RecordingWeather()

    with pytest.raises(error) as caught:
        await grid(request_, weather)

    assert weather.calls == []
    if reason is not None:
        assert isinstance(caught.value, InvalidRequest)
        assert caught.value.reason is reason


def test_the_point_cap_fixture_is_over_the_cap() -> None:
    assert len(route(CHICAGO, DENVER).points) * 14 > GRID_MAX_POINTS_PER_LINE
