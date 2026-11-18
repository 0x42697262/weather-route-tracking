"""Fixed values of the Open-Meteo adapter; reasons in `docs/facts.md` (F-28 to F-31, F-48).

`FORECAST_DAYS` 7 costs one API call per location and starts at 00:00 UTC of the current day,
so a payload fetched up to 24 hours earlier still covers `FORECAST_HORIZON_HOURS` from now.
`CELL_SIZE_DEG` 0.1 (about 11 km north-south) matches the global models that "best match"
falls back to (GFS about 13 km, F-29); a 3 km cell would multiply cells, calls and cache keys.
"""

FORECAST_DAYS = 7
HOURS_PER_DAY = 24
FORECAST_HORIZON_HOURS = (FORECAST_DAYS - 1) * HOURS_PER_DAY
HOUR_S = 3600

CELL_SIZE_DEG = 0.1
REQUEST_COORDINATE_DECIMALS = 4

BATCH_SIZE = 50
RATE_LIMIT_WAIT_BUDGET_S = 20.0
