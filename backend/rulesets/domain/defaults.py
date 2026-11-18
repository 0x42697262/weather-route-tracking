"""The default rule set document: the values in `docs/SPEC.md`, as staff would enter them.

Seeds the first version and is the reference document of `docs/rule-sets.md`.
"""

import copy
import json
from types import MappingProxyType
from typing import Final

_DEFAULT_DOCUMENT_JSON: Final = """
{
  "schema_version": 2,
  "conditions": [
    {
      "variable": "wind_speed",
      "unit": "mph",
      "bands": [
        {"level": "moderate", "from": 25, "inclusive": true},
        {"level": "high", "from": 35, "inclusive": true},
        {"level": "severe", "from": 45, "inclusive": true},
        {"level": "no_travel", "from": 55, "inclusive": true}
      ]
    },
    {
      "variable": "rain_rate",
      "unit": "in/h",
      "bands": [
        {"level": "moderate", "from": 0.10, "inclusive": true},
        {"level": "high", "from": 0.25, "inclusive": true},
        {"level": "severe", "from": 0.50, "inclusive": true},
        {"level": "no_travel", "from": 1.00, "inclusive": false}
      ]
    },
    {
      "variable": "snowfall_rate",
      "unit": "in/h",
      "bands": [
        {"level": "moderate", "from": 0.5, "inclusive": true},
        {"level": "high", "from": 1.0, "inclusive": true},
        {"level": "severe", "from": 2.0, "inclusive": true},
        {"level": "no_travel", "from": 3.0, "inclusive": false}
      ]
    }
  ],
  "load_rules": [
    {
      "variable": "wind_speed",
      "unit": "mph",
      "from": 45,
      "to": 55,
      "load_over": {"value": 30000, "unit": "lb"},
      "level": "no_travel"
    },
    {
      "variable": "wind_speed",
      "unit": "mph",
      "from": 35,
      "to": 45,
      "load_over": {"value": 40000, "unit": "lb"},
      "level": "severe"
    }
  ],
  "truck_speed_factor": 1.0,
  "truck_max_speed": {"value": 65, "unit": "mph"},
  "empty_vehicle_weight": {"value": 32500, "unit": "lb"},
  "rest_rules": {
    "enabled": true,
    "max_driving_before_break_hours": 8,
    "break_minutes": 30,
    "max_driving_per_shift_hours": 11,
    "max_shift_hours": 14,
    "off_duty_hours": 10
  },
  "stretch_method": "worse_end",
  "ferry_level": null,
  "max_unknown_share": 0.25,
  "checkpoint_spacings": [
    {"value": 10, "unit": "mi"},
    {"value": 25, "unit": "mi"},
    {"value": 50, "unit": "mi"}
  ],
  "default_checkpoint_spacing": {"value": 25, "unit": "mi"}
}
"""

_DEFAULT_DOCUMENT: Final = MappingProxyType(json.loads(_DEFAULT_DOCUMENT_JSON))


def default_rule_set_document() -> dict[str, object]:
    """A fresh, mutable copy of the default document."""
    return copy.deepcopy(dict(_DEFAULT_DOCUMENT))
