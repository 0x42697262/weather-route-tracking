# Testing

What is tested, with what, and what is left out of the first version. The general rules are in
`engineering-guidelines.md` section 12.

Scope for the first version: **backend rules tested fully, frontend lightly.**

## Backend

### Domain (pure, no mocks, parametrized tables)

| Module | Cases |
|---|---|
| `shared/units.py` | Each conversion against its exact factor; round trips |
| `planning/domain/risk.py` | Every band edge of every condition: just below, exactly on, just above. The two exclusive edges (rain 1.00 in/h, snow 3.0 in/h). Worst-of across conditions. `decided_by` |
| `planning/domain/risk.py` | Load rules: load exactly at the weight (no match) and just over (match); wind exactly at both ends of each range; a rule never lowers a level |
| `planning/domain/checkpoints.py` | Origin and destination always present; spacing longer than the route; last multiple near the destination dropped; positions interpolated on a known line; the cap |
| `planning/domain/timeline.py` | Truck speed: factor 1.0 and below 1.0; the cap applies only to segments above it; no cap; a provider with totals only |
| `planning/domain/timeline.py` | Rest clock: break exactly at 8 hours of driving; off duty at 11 hours of driving and at 14 hours of shift; a segment split at the limit; rest switched off by the trip option; under 8 hours of driving gives the same result on and off |
| `planning/domain/route_distinct.py` | Identical lines; fully separate lines; overlap just under and just over the limit; drive time just inside and outside the limit |
| `planning/domain/stretches.py` | Worse of two ends; Unknown end; distances per level add up to the route distance |
| `planning/domain/ranking.py` | Each key decides when the earlier ones tie; rounding prevents noise from deciding; every route with No Travel gives no recommendation; one route |
| `planning/domain/corridor.py` | Cells inside the buffer and none outside; cell size grows to respect the cap |
| `rulesets/domain/validator.py` | The default document passes; one failing document per rejection reason; several problems reported together |

Edge values are written in the unit the rule set uses and pass through the same conversion as
production code.

### Services (fake adapters, fixed clock)

In-memory fakes implement the provider protocols. Through `plan_trip`:

- a normal plan with 3 routes
- the provider's first answer has 3 routes: no extra request is made
- the first answer has 1 or 2: rounds run in order and stop at 3; a repeat of a kept route and a much slower route are dropped; unsupported rounds are skipped; the request cap holds
- rounds exhausted with 2 routes and with 1 route
- no route
- invalid spacing, past departure, departure beyond the forecast range: rejected **and** the fakes
  saw no call
- part of the weather missing: Unknown checkpoints and a warning
- all weather missing: no recommendation
- every route with No Travel
- a second identical request fetches no forecast cell again
- nothing from the route provider is written to the cache

Through `weather_grid`: a normal grid; route lines over the caps rejected before any outbound call.

### Adapters (`httpx.MockTransport`, recorded responses)

- Mapbox routing and geocoding, Open-Meteo: the request built (path, query, units), a recorded
  response parsed into domain objects in metric, a malformed response rejected, a timeout mapped to
  the named error, a retry on a retryable status.
- Recorded responses live under `tests/fixtures/` with keys removed.
- Live calls are opt-in (`@pytest.mark.live`) and skipped by default.

### API

One test per endpoint for success, plus validation failure and upstream failure mapped to the
error catalog. The readiness endpoint with and without an active rule set.

### Admin

Creating a version with a valid and an invalid document; activation leaves exactly one active; a
saved version cannot be edited.

## Frontend

- **Component tests:** unit conversion and formatting; the trip form (required fields, server error
  shown at its field); route cards (rank, warning, fewer-than-3 notice); the verdict line in its
  three states (recommendation, none, loading).
- **One end-to-end test** against a backend running with fake providers: fill the form, routes
  appear, the verdict line shows the recommendation, moving the slider changes the heatmap hour
  label.

## Checked by hand, recorded in the verification checklist

- Slider drag stays smooth on a phone (frame rate from the browser performance panel).
- The layout at phone, tablet and desktop widths.
- A real trip against the live providers after each deploy.

## Left out of the first version

Cross-browser runs, visual regression tests, load tests, and end-to-end coverage beyond the one
main flow.

## Commands

One verify command per side (`engineering-guidelines.md` section 13). GitHub Actions runs both, and
the contract check, on every push and pull request. Pushed tags additionally build the release
container images.
