"""Build the heatmap grid for the route lines the client holds (`docs/trip-planning.md`, Heatmap
grid). Every line is checked against the caps before any outbound call."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from planning import text
from planning.domain.corridor import CorridorCapUnreachable, build_corridor
from planning.domain.geometry import PolylineInvalid, decode_polyline, measure_line
from planning.domain.grid import HeatmapGrid, build_grid
from planning.domain.options import TripOptionsInput, build_options, resolve_options
from planning.domain.providers import WeatherProvider
from planning.domain.risk import rule_set_variables
from planning.domain.values import CellForecast, Coordinate
from planning.errors import InvalidRequest, PlanningError, Rejection
from planning.events import GRID_BUILT, GRID_REJECTED, GRID_REQUESTED
from planning.keys import FIELD_LINES, line_field
from planning.services.checks import check_departure, rejection_reason
from planning.services.constants import GRID_MAX_POINTS_PER_LINE
from planning.services.limits import PlanningLimits
from rulesets.domain.schema import VersionedRuleSet

logger = logging.getLogger(__name__)

MIN_POINTS_PER_LINE = 2


@dataclass(frozen=True, slots=True)
class GridRequest:
    """Encoded route lines, the departure and the load (metric)."""

    lines: tuple[str, ...]
    departure_utc: datetime
    load_kg: float


@dataclass(frozen=True, slots=True)
class WeatherGrid:
    """The classified grid and how the lookup went."""

    rule_set_version: int
    cell_size_deg: float
    grid: HeatmapGrid
    cells_missing: int


def _decoded_line(index: int, encoded: str, max_distance_km: float) -> tuple[Coordinate, ...]:
    field = line_field(index)
    try:
        points = decode_polyline(encoded)
    except PolylineInvalid:
        raise InvalidRequest(Rejection.LINE_INVALID, field, text.POLYLINE_INVALID) from None
    if len(points) < MIN_POINTS_PER_LINE:
        raise InvalidRequest(Rejection.LINE_INVALID, field, text.LINE_TOO_SHORT)
    if len(points) > GRID_MAX_POINTS_PER_LINE:
        raise InvalidRequest(
            Rejection.LINE_INVALID, field, text.line_too_many_points(GRID_MAX_POINTS_PER_LINE)
        )
    if measure_line(points).length_km > max_distance_km:
        raise InvalidRequest(Rejection.TRIP_TOO_LONG, field, text.LINE_TOO_LONG)
    return points


def _ordered(
    cells: Sequence[Coordinate], found: dict[Coordinate, CellForecast]
) -> list[CellForecast]:
    return [found.get(cell) or CellForecast(cell=cell, hours_utc=(), values={}) for cell in cells]


async def build_weather_grid(
    request: GridRequest,
    *,
    weather: WeatherProvider,
    rule_set: VersionedRuleSet,
    limits: PlanningLimits,
    now_utc: datetime,
) -> WeatherGrid:
    """Classify every corridor cell for every hour of the forecast window.

    Raises:
        TripOptionsInvalid: the load is outside the option registry.
        InvalidRequest: a line does not decode or breaks a cap, the departure is out of range,
            or the corridor cannot fit the cell cap. No provider was called.
    """
    logger.info(GRID_REQUESTED, extra={"lines": len(request.lines)})
    try:
        resolve_options(build_options(rule_set.rules), TripOptionsInput(load_kg=request.load_kg))
        check_departure(request.departure_utc, now_utc, weather.forecast_horizon_hours)
        lines = [
            _decoded_line(index, encoded, limits.trip_max_distance_km)
            for index, encoded in enumerate(request.lines)
        ]
        try:
            corridor = build_corridor(lines, weather.cell_size_deg, limits.weather_max_cells)
        except CorridorCapUnreachable:
            raise InvalidRequest(
                Rejection.CORRIDOR_TOO_LARGE, FIELD_LINES, text.CORRIDOR_TOO_LARGE
            ) from None
    except PlanningError as error:
        logger.info(GRID_REJECTED, extra={"reason": rejection_reason(error)})
        raise
    variables = frozenset(rule_set_variables(rule_set.rules))
    found = dict(await weather.forecasts(corridor.cells, variables, now_utc))
    grid = build_grid(
        _ordered(corridor.cells, found), request.departure_utc, request.load_kg, rule_set.rules
    )
    missing = sum(1 for cell in corridor.cells if cell not in found)
    logger.info(
        GRID_BUILT,
        extra={
            "cells": len(corridor.cells),
            "cell_size_deg": corridor.cell_size_deg,
            "hours": len(grid.hours_utc),
            "cells_missing": missing,
        },
    )
    return WeatherGrid(
        rule_set_version=rule_set.version,
        cell_size_deg=corridor.cell_size_deg,
        grid=grid,
        cells_missing=missing,
    )
