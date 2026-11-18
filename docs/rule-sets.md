# Rule sets

Business rules are data that staff manage in Django admin. This file covers the data shape, the
validator, versioning and the admin screens. The rule for where configuration lives is in
`engineering-guidelines.md` section 4.7.

## What a rule set holds (first version)

- Bands for three conditions: wind speed, rain, snow
- Load rules
- Truck: a speed factor, a speed cap and an empty vehicle weight
- Rest rules: break and off-duty limits, with an on/off switch
- The stretch method
- The allowed checkpoint spacings and the default one

Not in the first version: new conditions, an editable ranking order, the forecast window and the
number of routes. The last two are fixed constants for now.

## Data shape

One JSON document per version. Thresholds keep the unit they were entered in.

```json
{
  "schema_version": 2,
  "conditions": [
    {
      "variable": "wind_speed",
      "unit": "mph",
      "bands": [
        { "level": "moderate", "from": 25, "inclusive": true },
        { "level": "high", "from": 35, "inclusive": true },
        { "level": "severe", "from": 45, "inclusive": true },
        { "level": "no_travel", "from": 55, "inclusive": true }
      ]
    },
    {
      "variable": "rain_rate",
      "unit": "in/h",
      "bands": [
        { "level": "moderate", "from": 0.10, "inclusive": true },
        { "level": "high", "from": 0.25, "inclusive": true },
        { "level": "severe", "from": 0.50, "inclusive": true },
        { "level": "no_travel", "from": 1.00, "inclusive": false }
      ]
    },
    {
      "variable": "snowfall_rate",
      "unit": "in/h",
      "bands": [
        { "level": "moderate", "from": 0.5, "inclusive": true },
        { "level": "high", "from": 1.0, "inclusive": true },
        { "level": "severe", "from": 2.0, "inclusive": true },
        { "level": "no_travel", "from": 3.0, "inclusive": false }
      ]
    }
  ],
  "load_rules": [
    {
      "variable": "wind_speed",
      "unit": "mph",
      "from": 45,
      "to": 55,
      "load_over": { "value": 30000, "unit": "lb" },
      "level": "no_travel"
    },
    {
      "variable": "wind_speed",
      "unit": "mph",
      "from": 35,
      "to": 45,
      "load_over": { "value": 40000, "unit": "lb" },
      "level": "severe"
    }
  ],
  "truck_speed_factor": 1.0,
  "truck_max_speed": { "value": 65, "unit": "mph" },
  "empty_vehicle_weight": { "value": 32500, "unit": "lb" },
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
    { "value": 10, "unit": "mi" },
    { "value": 25, "unit": "mi" },
    { "value": 50, "unit": "mi" }
  ],
  "default_checkpoint_spacing": { "value": 25, "unit": "mi" }
}
```

Where the defaults come from: thresholds and load rules from `SPEC.md`; the speed cap and rest
rules from the sources in `facts.md` (F-13, F-16 to F-19); the empty vehicle weight from EPA's
measured tractor and trailer weights (F-53). Both stretch methods (`worse_end`, `refine`) and the
rest clock are built; the options endpoint reports the method in effect (`stretch_method`).

`rest_rules.enabled` is the default of the driver's per-trip option, not a lock: a driver can turn
rest off for one trip (`trip-planning.md`).

Because a band is only a lower bound, bands cannot have gaps or overlaps. Everything below the
first band is Low.

## From document to domain object

`validate_rule_set(data) -> RuleSet` in `rulesets/domain/` is the only way a document becomes a
`RuleSet`. It is pure. It converts every threshold to the metric unit once and returns a frozen
object; the planning domain only ever sees metric values.

It rejects, reporting **every** problem at once:

- unknown `schema_version`, missing or extra keys
- a variable outside the `WeatherVariable` enum, or a unit not valid for that variable
- a level outside the five levels, or a "low" band
- bands not strictly ascending in bound, or not ascending in level
- a load rule whose `from` is not below its `to`, or whose weight is not positive
- a speed factor, speed cap or empty vehicle weight outside its bounds (the cap may be `null`,
  meaning none)
- rest rules that are not positive, a break limit above the shift driving limit, or a driving limit
  above the shift length
- a stretch method that is not in the method table
- a `ferry_level` that is neither `null` nor one of the five levels
- a `max_unknown_share` that is neither `null` nor a number from 0 to 1
- an empty spacing list, or a default spacing not in the list
- more bands or rules than the caps in `rulesets/constants.py`
- an empty condition list or an empty band list, two conditions for the same variable, or the
  same spacing twice (an empty list would rate everything Low without anyone noticing)

Caps and bounds (`rulesets/constants.py`): at most 20 conditions, 10 bands per condition, 20 load
rules and 10 spacings; speed factor 0.5 to 1.5; speed cap 30 to 160 km/h; empty vehicle weight
1,000 to 40,000 kg. Bounds are checked after conversion to metric.

### Schema versions

| `schema_version` | Keys | Read as |
|---|---|---|
| 1 | Everything above except `max_unknown_share` | `max_unknown_share` = `null` (no limit), which is how version-1 documents behaved |
| 2 | All keys above | As written |

Published versions are never rewritten, so a schema-1 version still gives the result it gave when
it was active. Migration `0003_add_max_unknown_share` upgrades the database once: if the active
version is schema 1, it publishes its document as a new schema-2 version with
`max_unknown_share: 0.25` and activates it; the old version stays, read-only. New documents must
use schema 2 (the admin form is pre-filled with the active document).

Each problem names its place with a path such as `conditions[0].bands[2].from` (`$` is the whole
document). An unknown `schema_version` is reported alone, because the rest of the document cannot
be read without it. The error is `RuleSetInvalid(problems)`.

The same function is called by the admin form (`Model.clean()`), the seed migration and the loader.

## Storage and versions

Model `RuleSetVersion`: `version` (unique, increasing), `data` (JSON), `note`, `is_active`,
`created_by`, `created_at`, `activated_by`, `activated_at`.

- A saved version is immutable. A change is always a new version.
- A database constraint allows exactly one active version.
- Rollback is activating an earlier version.
- `save()` refuses any update of a saved row except its activation fields; activation and
  creation go through `rulesets/services/versions.py` (`create_version`, `activate_version`).
- A data migration creates version 1 from `rulesets/domain/defaults.py` (the values in `SPEC.md`)
  and activates it.
- The readiness endpoint fails when no version is active.

## Admin screens

Plain Django admin, staff accounts only, at the path given by the `ADMIN_URL` setting.

- **List:** version, note, active flag, who and when.
- **Add:** the JSON document (pre-filled from the active version) and a note. Saving runs the
  validator and shows every problem next to the field.
- **Activate:** an action on a saved version. Records who and when.
- Saved versions open read-only. There is no delete for a version that was ever active.

As built: activating needs the `rulesets.activate_rulesetversion` permission (superusers have it)
and exactly one selected version; the admin log records each activation. No version can be
deleted at all, active or not, which is the simplest way to meet the rule above and keeps every
past result traceable.

## How the rest of the app uses it

- A service function returns the active `RuleSet`, cached under a key that includes the version.
  Activation changes which version is looked up, so no cache flush is needed.
  (`rulesets/services/active.py`: one cheap query for the active version number and creation
  time per call; the key also holds the creation time and a payload version, so a database reset
  that reuses a number cannot serve a stale entry. Entries expire after one day.)
- Every trip response carries `rule_set_version`.
- `GET /api/v1/options` exposes what the driver may choose (spacings, default) from the active
  rule set, so the frontend hard-codes none of it.

## Options endpoint (as built)

`GET /api/v1/options` answers from `planning/domain/options.py` (the option registry) and the
shared tables. Shape:

```json
{
  "rule_set_version": 1,
  "forecast_window_hours": 48,
  "options": {
    "checkpoint_spacing": {
      "name": "checkpoint_spacing", "tier": "basic", "text_key": "checkpoint_spacing",
      "available": true, "unit": "km",
      "choices": [{ "value": 10, "unit": "mi", "km": 16.09344 }, "..."],
      "default": { "value": 25, "unit": "mi", "km": 40.2336 }
    },
    "include_rest_stops": {
      "name": "include_rest_stops", "tier": "advanced", "text_key": "include_rest_stops",
      "available": true, "default": true
    },
    "load_weight": {
      "name": "load_weight", "tier": "basic", "text_key": "load_weight", "available": true,
      "unit": "kg", "required": true, "default": null, "minimum": 0, "maximum": 50000
    }
  },
  "risk_levels": [
    { "key": "low", "score": 0, "ranked": false, "blocks_recommendation": false,
      "text_key": "low", "color_key": "risk-low" }, "..."
  ],
  "weather_variables": [{ "key": "wind_speed", "metric_unit": "km/h", "text_key": "wind_speed" }, "..."],
  "heatmap_layers": {
    "default": "risk",
    "layers": [{ "key": "risk", "variable": null, "text_key": "combined_risk" }, "..."]
  }
}
```

Decisions:

- **Load weight is required** (no default). `SPEC.md` lists it as an input, not an option, and any
  default would quietly change which load rules apply. Bounds 0 to 50,000 kg, inclusive: well
  above a legal US load, so a permit load still plans (with the over-80,000 lb warning), while an
  extra zero is rejected.
- **Rest stops** are available. The trip option's default is the rule set's
  `rest_rules.enabled`.
- Spacings are matched in km with a relative tolerance of 1e-9, so `{25, mi}` and `40.2336 km`
  are the same choice.
- Values outside the registry are rejected with `invalid_request` and one detail per option; they
  are never clamped.

Every API error has one envelope:
`{"error": {"code": "<ErrorCode>", "message": "<catalog text>", "details": [{"field", "message"}] | null}}`.
The status comes from a table in `core/api.py`: `invalid_request` 400 (schema failures too, with
the field path in `details`), `no_road_route` 422, `place_not_found` 404,
`upstream_unavailable` and `upstream_invalid_response` 502, `upstream_busy` and
`no_active_rule_set` 503, `rate_limited` 429. Messages are in `planning/text.py`.

## Log events

`rule_set.created`, `rule_set.activated` (version, user), `rule_set.rejected` (problem count).
