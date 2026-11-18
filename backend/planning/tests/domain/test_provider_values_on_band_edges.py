from datetime import UTC, datetime, timedelta

import pytest

from planning.adapters.open_meteo.protocol import parse_forecasts
from planning.domain.risk import classify, rule_set_variables
from planning.domain.values import Coordinate
from planning.domain.weather_lookup import values_at
from rulesets.domain.defaults import default_rule_set_document
from rulesets.domain.validator import validate_rule_set
from shared.risk_levels import RiskLevel

RULES = validate_rule_set(default_rule_set_document())
FIRST_HOUR_S = 1_800_000_000 - 1_800_000_000 % 3600
CELL = Coordinate(40.0, -100.0)


def _classify_raw(
    rain_mm: float, showers_mm: float, snowfall_cm: float, wind_kmh: float
) -> RiskLevel | None:
    payload = {
        "hourly_units": {
            "time": "unixtime",
            "rain": "mm",
            "showers": "mm",
            "snowfall": "cm",
            "wind_speed_10m": "km/h",
        },
        "hourly": {
            "time": [FIRST_HOUR_S, FIRST_HOUR_S + 3600],
            "rain": [rain_mm, rain_mm],
            "showers": [showers_mm, showers_mm],
            "snowfall": [snowfall_cm, snowfall_cm],
            "wind_speed_10m": [wind_kmh, wind_kmh],
        },
    }
    variables = rule_set_variables(RULES)
    (forecast,) = parse_forecasts(payload, [CELL], frozenset(variables))
    arrival = datetime.fromtimestamp(FIRST_HOUR_S, UTC) + timedelta(minutes=10)
    return classify(values_at(forecast, arrival, variables), 0, RULES).level


@pytest.mark.parametrize(
    ("rain_mm", "showers_mm", "snowfall_cm", "wind_kmh", "expected"),
    [
        (25.4, 0.0, 0.0, 0.0, RiskLevel.SEVERE),
        (0.1, 25.3, 0.0, 0.0, RiskLevel.SEVERE),
        (12.6, 12.8, 0.0, 0.0, RiskLevel.SEVERE),
        (0.1, 25.4, 0.0, 0.0, RiskLevel.NO_TRAVEL),
        (0.0, 0.0, 7.62, 0.0, RiskLevel.SEVERE),
        (0.0, 0.0, 7.63, 0.0, RiskLevel.NO_TRAVEL),
        (0.0, 0.0, 5.08, 0.0, RiskLevel.SEVERE),
        (0.0, 0.0, 0.0, 56.32704, RiskLevel.HIGH),
        (0.0, 0.0, 0.0, 88.51392, RiskLevel.NO_TRAVEL),
    ],
)
def test_raw_provider_values_on_an_edge_take_the_documented_level(
    rain_mm: float, showers_mm: float, snowfall_cm: float, wind_kmh: float, expected: RiskLevel
) -> None:
    assert _classify_raw(rain_mm, showers_mm, snowfall_cm, wind_kmh) is expected
