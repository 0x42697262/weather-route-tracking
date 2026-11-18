"""Request field types shared by the trip and weather grid endpoints, and their conversion to
metric and UTC.

Quantities arrive as a value and a unit; the schema checks the unit's dimension, and the view
converts to the canonical metric unit, once.
"""

from datetime import UTC, datetime
from typing import Annotated, ClassVar, Self

from ninja import Schema
from pydantic import ConfigDict, Field, model_validator

from planning import text
from shared.units import METRIC_UNIT_BY_DIMENSION, Dimension, Unit, convert, units_of

MAX_LATITUDE = 90.0
MAX_LONGITUDE = 180.0

Latitude = Annotated[float, Field(ge=-MAX_LATITUDE, le=MAX_LATITUDE, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-MAX_LONGITUDE, le=MAX_LONGITUDE, allow_inf_nan=False)]


class _QuantityIn(Schema):
    """A number and the unit it is written in; the unit must measure `dimension`."""

    model_config = ConfigDict(extra="forbid")
    dimension: ClassVar[Dimension]

    value: Annotated[float, Field(allow_inf_nan=False)]
    unit: Unit

    @model_validator(mode="after")
    def _unit_measures_dimension(self) -> Self:
        allowed = units_of(self.dimension)
        if self.unit not in allowed:
            raise ValueError(text.unit_not_allowed(sorted(unit.value for unit in allowed)))
        return self

    def metric(self) -> float:
        """The value in the dimension's metric unit."""
        return convert(self.value, self.unit, METRIC_UNIT_BY_DIMENSION[self.dimension])


class MassIn(_QuantityIn):
    """A weight: `kg`, `lb` or `t`."""

    dimension: ClassVar[Dimension] = Dimension.MASS


class DistanceIn(_QuantityIn):
    """A distance: `km`, `mi` or `m`."""

    dimension: ClassVar[Dimension] = Dimension.DISTANCE


def to_utc(moment: datetime) -> datetime:
    """An aware datetime in UTC."""
    return moment.astimezone(UTC)
