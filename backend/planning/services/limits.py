"""The operator bounds the planning services work within, read from settings by `core.wiring`."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlanningLimits:
    """Bounds from the environment (`docs/configuration.md`, Bounds)."""

    trip_max_distance_km: float
    max_checkpoints_per_route: int
    route_alternatives_requested: int
    route_max_extra_requests: int
    weather_max_cells: int
