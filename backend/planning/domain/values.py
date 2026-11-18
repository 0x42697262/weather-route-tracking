"""Value objects shared by planning domain code, services and adapters. All metric, all UTC."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from shared.weather_variables import WeatherVariable


@dataclass(frozen=True, slots=True)
class Coordinate:
    """A WGS84 position in decimal degrees."""

    latitude: float
    longitude: float


class RouteSource(StrEnum):
    """How a kept route was found; the route card shows its label."""

    FASTEST = "fastest"
    ALTERNATIVE = "alternative"
    AVOID_TOLLS = "avoid_tolls"
    AVOID_HIGHWAYS = "avoid_highways"
    DETOUR = "detour"


class Avoidance(StrEnum):
    """Road types a routing request can avoid."""

    TOLL_ROADS = "toll_roads"
    MOTORWAYS = "motorways"


@dataclass(frozen=True, slots=True)
class Vehicle:
    """The truck sent to the routing provider."""

    weight_kg: float
    max_speed_kmh: float | None


@dataclass(frozen=True, slots=True)
class RouteRequest:
    """One routing request. `via` points are visited in order between origin and destination."""

    origin: Coordinate
    destination: Coordinate
    departure_utc: datetime
    vehicle: Vehicle
    alternatives: int
    avoid: frozenset[Avoidance]
    via: tuple[Coordinate, ...]


@dataclass(frozen=True, slots=True)
class ProgressPoint:
    """Cumulative distance and provider drive time at a point index of the route line."""

    point_index: int
    distance_km: float
    elapsed_s: float


@dataclass(frozen=True, slots=True)
class PointRange:
    """An inclusive range of point indexes on a route line."""

    start_index: int
    end_index: int


@dataclass(frozen=True, slots=True)
class ProviderRoute:
    """A route as the provider returned it, parsed to metric and UTC.

    `progress` starts at index 0 and ends at the last point. Times in it are the provider's truck
    driving times, before this app's speed factor, cap or rest.
    """

    points: tuple[Coordinate, ...]
    distance_km: float
    travel_time_s: float
    progress: tuple[ProgressPoint, ...]
    ferry_sections: tuple[PointRange, ...]


@dataclass(frozen=True, slots=True)
class PlaceSuggestion:
    """One place-search suggestion. It has no coordinates; picking it costs a details call."""

    place_id: str
    title: str
    subtitle: str


@dataclass(frozen=True, slots=True)
class Place:
    """A picked place with its coordinates."""

    place_id: str
    label: str
    coordinate: Coordinate


@dataclass(frozen=True, slots=True)
class CellForecast:
    """Hourly forecast for one weather grid cell.

    `hours_utc` are consecutive whole hours. `values[variable][index]` is the metric value at
    `hours_utc[index]` as the provider reports it (see `Aggregation`), or None when missing.
    """

    cell: Coordinate
    hours_utc: tuple[datetime, ...]
    values: dict[WeatherVariable, tuple[float | None, ...]]


@dataclass(frozen=True, slots=True)
class TripOptions:
    """The resolved trip parameters, metric."""

    checkpoint_spacing_km: float
    include_rest_stops: bool
    load_kg: float
