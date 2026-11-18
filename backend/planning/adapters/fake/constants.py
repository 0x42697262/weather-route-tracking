"""Fixed values of the fake providers: synthetic route shapes and speeds, the weather pattern and
the place table (`docs/configuration.md`, "Fake providers")."""

from typing import Final

ROUTE_POINT_SPACING_KM: Final = 1.0
ROUTE_MAX_POINTS: Final = 5000
ROUTE_MIN_POINTS: Final = 2
ROUTE_MAX_ALTERNATIVES: Final = 2

FASTEST_BOW_SHARE: Final = 0.0
FASTEST_SPEED_KMH: Final = 85.0
NORTH_BOW_SHARE: Final = 0.12
NORTH_SPEED_KMH: Final = 80.0
SOUTH_BOW_SHARE: Final = -0.18
SOUTH_SPEED_KMH: Final = 78.0

CELL_SIZE_DEG: Final = 0.1
FORECAST_HORIZON_HOURS: Final = 144
HOURS_PER_DAY: Final = 24

WIND_BASE_KMH: Final = 20.0
WIND_SWING_KMH: Final = 75.0
WIND_SHARPNESS: Final = 2
WIND_LATITUDE_RAD_PER_DEG: Final = 1.2
WIND_LONGITUDE_RAD_PER_DEG: Final = 0.8
WIND_RAD_PER_HOUR: Final = 0.05

RAIN_SWING_MM_PER_H: Final = 8.0
RAIN_SHARPNESS: Final = 2
RAIN_LATITUDE_RAD_PER_DEG: Final = 1.1
RAIN_LONGITUDE_RAD_PER_DEG: Final = 0.7
RAIN_RAD_PER_HOUR: Final = 0.15

SNOW_SWING_CM_PER_H: Final = 2.0
SNOW_FROM_LATITUDE_DEG: Final = 40.0
SNOW_LONGITUDE_RAD_PER_DEG: Final = 0.9
SNOW_RAD_PER_HOUR: Final = 0.1

VALUE_DECIMALS: Final = 2
