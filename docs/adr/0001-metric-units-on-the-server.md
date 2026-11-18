# 0001. Metric units on the server

Status: accepted, 2026-11-16

## Context

The default thresholds are written in imperial units (mph, in/h, lb, miles). The weather and
routing providers answer in metric. Drivers may want either system on screen. Mixing units inside
calculations is a common source of wrong results.

## Decision

The server computes in metric only: km, km/h, mm/h, cm/h, kg, seconds, UTC. Anything in another
unit is converted exactly once, at a boundary: provider responses in the adapter, rule set
thresholds when the rule set is loaded, driver input at the API. Rule set thresholds are stored in
the unit staff entered. The API returns metric. The frontend converts for display; imperial is the
default display preference.

## Consequences

- Names carry metric units (`wind_speed_kmh`, `distance_km`, `load_kg`).
- Default thresholds become non-round metric numbers internally (25 mph is 40.2336 km/h). Tests
  write edges in the rule set's unit and convert through the production function.
- Changing the display unit never changes a result.
