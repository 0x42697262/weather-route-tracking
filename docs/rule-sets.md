# Rule sets

Business rules are data that staff manage in Django admin. This file covers the data shape, the
validator, versioning and the admin screens. The rule for where configuration lives is in
`engineering-guidelines.md` section 4.7.

## What a rule set holds (first version)

- Bands for three conditions: wind speed, rain, snow
- Load rules
- Truck speed: a factor and a speed cap
- Rest rules: break and off-duty limits, with an on/off switch
- The stretch method
- The allowed checkpoint spacings and the default one

Not in the first version: new conditions, an editable ranking order, the forecast window and the
number of routes. The last two are fixed constants for now.

## Data shape

One JSON document per version. Thresholds keep the unit they were entered in.

```json
{
  "schema_version": 1,
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
  "rest_rules": {
    "enabled": true,
    "max_driving_before_break_hours": 8,
    "break_minutes": 30,
    "max_driving_per_shift_hours": 11,
    "max_shift_hours": 14,
    "off_duty_hours": 10
  },
  "stretch_method": "worse_end",
  "checkpoint_spacings": [
    { "value": 10, "unit": "mi" },
    { "value": 25, "unit": "mi" },
    { "value": 50, "unit": "mi" }
  ],
  "default_checkpoint_spacing": { "value": 25, "unit": "mi" }
}
```

Where the defaults come from: thresholds and load rules from `SPEC.md`; the speed cap and rest
rules from the sources in `facts.md` (F-13, F-16 to F-19).

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
- a speed factor or speed cap outside its bounds (the cap may be `null`, meaning none)
- rest rules that are not positive, a break limit above the shift driving limit, or a driving limit
  above the shift length
- a stretch method that is not in the method table
- an empty spacing list, or a default spacing not in the list
- more bands or rules than the caps in `rulesets/constants.py`

The same function is called by the admin form (`Model.clean()`), the seed migration and the loader.

## Storage and versions

Model `RuleSetVersion`: `version` (unique, increasing), `data` (JSON), `note`, `is_active`,
`created_by`, `created_at`, `activated_by`, `activated_at`.

- A saved version is immutable. A change is always a new version.
- A database constraint allows exactly one active version.
- Rollback is activating an earlier version.
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

## How the rest of the app uses it

- A service function returns the active `RuleSet`, cached under a key that includes the version.
  Activation changes which version is looked up, so no cache flush is needed.
- Every trip response carries `rule_set_version`.
- `GET /api/v1/options` exposes what the driver may choose (spacings, default) from the active
  rule set, so the frontend hard-codes none of it.

## Log events

`rule_set.created`, `rule_set.activated` (version, user), `rule_set.rejected` (problem count).
