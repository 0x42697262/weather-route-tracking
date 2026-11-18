"""Request and response schemas of `POST /api/v1/weather-grid` (the contract).

The response is compact: cells are parallel arrays, levels are small integers indexing the
`levels` list, and values are rounded (`docs/trip-planning.md`, Heatmap grid).
"""

from datetime import datetime
from typing import Annotated

from ninja import Schema
from pydantic import AwareDatetime, ConfigDict, Field

from planning.api.inputs import MassIn, to_utc
from planning.domain.grid import ConditionSeries, HeatmapGrid
from planning.domain.options import HEATMAP_LAYERS
from planning.services.constants import (
    GRID_MAX_ENCODED_CHARS,
    GRID_MAX_LINES,
    GRID_VALUE_DECIMALS,
    OUTPUT_COORDINATE_DECIMALS,
)
from planning.services.weather_grid import GridRequest, WeatherGrid
from shared.risk_levels import LEVELS_BY_SCORE, RiskLevel
from shared.weather_variables import WeatherVariable

EncodedLine = Annotated[str, Field(min_length=1, max_length=GRID_MAX_ENCODED_CHARS)]


class WeatherGridIn(Schema):
    """The route lines the client holds (the `polyline` of each route), the departure and the
    load."""

    model_config = ConfigDict(extra="forbid")

    lines: Annotated[list[EncodedLine], Field(min_length=1, max_length=GRID_MAX_LINES)]
    departure_utc: AwareDatetime
    load_weight: MassIn


def grid_request(payload: WeatherGridIn) -> GridRequest:
    """The service request: metric load and a UTC departure."""
    return GridRequest(
        lines=tuple(payload.lines),
        departure_utc=to_utc(payload.departure_utc),
        load_kg=payload.load_weight.metric(),
    )


class GridLayerOut(Schema):
    """One heatmap layer. `levels[cell][hour]` indexes the response's `levels` (null: no
    forecast). `values[cell][hour]` is the metric value; null for the combined layer."""

    key: str
    variable: WeatherVariable | None
    text_key: str
    levels: list[list[int | None]]
    values: list[list[float | None]] | None


class WeatherGridOut(Schema):
    """Every corridor cell for every hour from departure to departure plus the window."""

    rule_set_version: int
    departure_utc: datetime
    hours_utc: list[datetime]
    cell_size_deg: float
    levels: list[RiskLevel]
    latitudes: list[float]
    longitudes: list[float]
    layers: list[GridLayerOut]
    cells_missing: int


LEVEL_INDEX = {level: index for index, level in enumerate(LEVELS_BY_SCORE)}


def _level_indexes(levels: tuple[RiskLevel | None, ...]) -> list[int | None]:
    return [None if level is None else LEVEL_INDEX[level] for level in levels]


def _values(values: tuple[float | None, ...]) -> list[float | None]:
    return [None if value is None else round(value, GRID_VALUE_DECIMALS) for value in values]


def _series(grid: HeatmapGrid, variable: WeatherVariable) -> list[ConditionSeries]:
    return [
        series for cell in grid.cells for series in cell.conditions if series.variable is variable
    ]


def _layers(grid: HeatmapGrid) -> list[GridLayerOut]:
    layers: list[GridLayerOut] = []
    for layer in HEATMAP_LAYERS:
        if layer.variable is None:
            layers.append(
                GridLayerOut(
                    key=layer.key,
                    variable=None,
                    text_key=layer.text_key,
                    levels=[_level_indexes(cell.combined) for cell in grid.cells],
                    values=None,
                )
            )
            continue
        if layer.variable not in grid.variables:
            continue
        series = _series(grid, layer.variable)
        layers.append(
            GridLayerOut(
                key=layer.key,
                variable=layer.variable,
                text_key=layer.text_key,
                levels=[_level_indexes(item.levels) for item in series],
                values=[_values(item.values) for item in series],
            )
        )
    return layers


def weather_grid_out(result: WeatherGrid) -> WeatherGridOut:
    """The compact response for a built grid."""
    grid = result.grid
    return WeatherGridOut(
        rule_set_version=result.rule_set_version,
        departure_utc=grid.hours_utc[0],
        hours_utc=list(grid.hours_utc),
        cell_size_deg=result.cell_size_deg,
        levels=list(LEVELS_BY_SCORE),
        latitudes=[round(cell.center.latitude, OUTPUT_COORDINATE_DECIMALS) for cell in grid.cells],
        longitudes=[
            round(cell.center.longitude, OUTPUT_COORDINATE_DECIMALS) for cell in grid.cells
        ],
        layers=_layers(grid),
        cells_missing=result.cells_missing,
    )
