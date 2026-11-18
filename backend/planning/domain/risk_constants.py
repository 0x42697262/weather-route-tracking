"""Fixed internal constants of risk classification, weather lookup, stretches, ranking and the
heatmap grid (`docs/risk-model.md`, `docs/trip-planning.md`)."""

from datetime import timedelta
from typing import Final

FORECAST_WINDOW_HOURS: Final = 48
FORECAST_STEP: Final = timedelta(hours=1)

CELL_KEY_DECIMALS: Final = 6
HALF_STEP: Final = 0.5

DECIDED_BY_SEPARATOR: Final = ":"

RANKING_DISTANCE_DECIMALS: Final = 2
RANKING_AVERAGE_RISK_DECIMALS: Final = 3
RANKING_TRAVEL_TIME_DECIMALS: Final = 0
LEVEL_DISTANCE_KEY_SUFFIX: Final = "_km"
AVERAGE_RISK_KEY: Final = "average_risk"
TRAVEL_TIME_KEY: Final = "travel_time_s"

REFINE_MAX_DEPTH: Final = 4

UNKNOWN_SHARE_DECIMALS: Final = 4
