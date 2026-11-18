"""The provider protocols services depend on. One adapter per vendor implements each."""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Protocol

from planning.domain.values import (
    Avoidance,
    CellForecast,
    Coordinate,
    Place,
    PlaceSuggestion,
    ProviderRoute,
    RouteRequest,
)
from shared.weather_variables import WeatherVariable


class RouteProvider(Protocol):
    """Truck routing."""

    @property
    def supported_avoidances(self) -> frozenset[Avoidance]:
        """Avoidances this provider accepts; top-up rounds needing others are skipped."""
        ...

    @property
    def supports_via(self) -> bool:
        """Whether requests may carry via points (the detour round)."""
        ...

    @property
    def max_alternatives(self) -> int:
        """Most alternatives one request may ask for."""
        ...

    async def routes(self, request: RouteRequest) -> tuple[ProviderRoute, ...]:
        """The fastest route first, then the provider's alternatives.

        Raises:
            NoRoadRoute: the provider found no road link.
            UpstreamUnavailable, UpstreamBusy, UpstreamInvalidResponse: see `planning.errors`.
        """
        ...


class Geocoder(Protocol):
    """Place search."""

    async def suggest(self, query: str, session_id: str) -> tuple[PlaceSuggestion, ...]:
        """Suggestions for a partial query."""
        ...

    async def details(self, place_id: str) -> Place:
        """The coordinates of a suggestion.

        Raises:
            PlaceNotFound: the id is unknown.
        """
        ...


class WeatherProvider(Protocol):
    """Hourly forecasts on the provider's grid."""

    @property
    def cell_size_deg(self) -> float:
        """Grid step in degrees used to round positions to cells."""
        ...

    @property
    def forecast_horizon_hours(self) -> int:
        """Hours from the current hour that a fetch covers."""
        ...

    async def forecasts(
        self,
        cells: Sequence[Coordinate],
        variables: frozenset[WeatherVariable],
        now_utc: datetime,
    ) -> Mapping[Coordinate, CellForecast]:
        """Forecasts for the cells, keyed by the requested cell. Cells that failed are absent."""
        ...
