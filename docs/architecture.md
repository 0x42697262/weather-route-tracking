# Architecture

The module map for the backend and the frontend, and the path of a request through them. Layer
rules are in `engineering-guidelines.md` sections 2 and 3. Package names below are the intended
ones; nothing is scaffolded yet.

## Request path

    browser
      -> Caddy (HTTPS, compression, static frontend files)
      -> Django (ASGI)
           middleware: request id, rate limit, CORS
           -> view (planning/api/views.py): validate, call one service
           -> service (planning/services/): ordered checks, calls adapters and domain
                -> adapters: route provider, geocoder, weather provider, cache, database
                -> domain (pure): checkpoints, classification, stretches, ranking, corridor
           -> response schema
      <- JSON (metric units, UTC times, rule_set_version, options_used)

The frontend converts units for display and draws. It computes no risk, ranking or threshold.

## Backend

| Stage | Code | Notes |
|---|---|---|
| Boot | `core/env.py` | The only place environment variables are read; typed and validated |
| Boot | `core/settings.py` | Django settings built from `env.py` |
| Wiring | `core/wiring.py` | Builds adapters and services from settings; picks providers by name |
| HTTP | `core/api.py`, `core/urls.py` | API router, version prefix, exception handler mapping named errors to the error catalog |
| Entry | `planning/api/views.py` | Thin async views |
| Contract | `planning/api/schemas.py` | Request and response schemas; the source of the OpenAPI document |
| Use cases | `planning/services/plan_trip.py` | Plan a trip (`trip-planning.md`) |
| Use cases | `planning/services/route_options.py` | Top up to 3 distinct routes |
| Use cases | `planning/services/weather_grid.py` | Build the heatmap grid |
| Use cases | `planning/services/places.py` | Place suggestions |
| Domain | `planning/domain/values.py` | `Coordinate`, `Route`, `Checkpoint`, `Stretch`, `RouteSummary`, `WeatherSample`, `TripOptions` |
| Domain | `planning/domain/checkpoints.py` | Checkpoint placement |
| Domain | `planning/domain/timeline.py` | Truck speed, rest stops, arrival times |
| Domain | `planning/domain/route_distinct.py` | Whether a route is distinct from those already kept |
| Domain | `planning/domain/risk.py` | Classification with bands and load rules |
| Domain | `planning/domain/stretches.py` | Stretch levels and per-route summaries |
| Domain | `planning/domain/ranking.py` | Ranking key and recommendation |
| Domain | `planning/domain/corridor.py` | Grid cells around the routes |
| Domain | `planning/domain/options.py` | The trip option registry |
| Domain | `planning/domain/providers.py` | `RouteProvider`, `Geocoder`, `WeatherProvider` protocols |
| Adapters | `planning/adapters/mapbox/` | Routing and geocoding: `client.py`, `protocol.py` |
| Adapters | `planning/adapters/open_meteo/` | Forecasts: `client.py`, `protocol.py` |
| Adapters | `planning/adapters/forecast_cache.py` | Forecast cells in the Django cache |
| Catalogs | `planning/constants.py`, `keys.py`, `text.py`, `events.py`, `errors.py` | One home per kind of value |
| Rules | `rulesets/domain/schema.py`, `validator.py`, `defaults.py` | Rule set types, the one validator, the seed values |
| Rules | `rulesets/models.py`, `admin.py`, `migrations/` | Versions in the database, admin screens, seed migration |
| Rules | `rulesets/services/active.py` | Returns the active `RuleSet` |
| Shared | `shared/units.py` | Exact unit conversion |
| Shared | `shared/risk_levels.py` | The risk level table |
| Shared | `shared/weather_variables.py` | The weather condition table |

`planning/domain/` and `rulesets/domain/` import nothing from Django, the HTTP client or any
adapter. A lint rule enforces it.

## Frontend

| Area | Code | Notes |
|---|---|---|
| Boot | `src/config/` | Validated public settings (API base URL, tile source) |
| Contract | `src/api/` | Types generated from the OpenAPI document, and a typed client |
| Server state | `src/api/queries.ts` | TanStack Query hooks: options, places, trip, weather grid |
| Trip form | `src/features/trip-form/` | Places inputs, departure, load, spacing |
| Routes | `src/features/routes/` | Verdict line, route cards, route details, checkpoint details |
| Map | `src/features/map/` | The map, route lines, checkpoints, truck markers |
| Heatmap | `src/features/heatmap/` | Layer choice, time slider, the heatmap layer |
| Sheet | `src/features/sheet/` | Bottom sheet with three heights; side panel on wide screens |
| Preferences | `src/features/preferences/` | Units, map style; versioned `localStorage` |
| Display | `src/lib/units.ts`, `src/lib/format.ts` | Metric to display units, time and duration formatting |
| Catalogs | `src/text/`, `src/keys.ts`, `src/constants.ts`, `src/theme/` | Strings, ids, constants, color tokens |
| Primitives | `src/components/ui/` | Library components (`frontend.md`) |

## Data that persists

| Data | Where | Versioned by |
|---|---|---|
| Rule set versions | Database | `version` column, `schema_version` in the document |
| Forecast cells | Cache | Version in the cache key |
| Driver preferences | Browser `localStorage` | `schemaVersion` in the stored object |

Nothing is stored per driver on the server, and route results from a provider are never stored
(`trip-planning.md`).

## Decisions

Each significant choice has an ADR in `docs/adr/`.
