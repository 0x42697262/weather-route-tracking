# Architecture

The module map for the backend and the frontend, and the path of a request through them. Layer
rules are in `engineering-guidelines.md` sections 2 and 3. Backend rows name files that exist.

## Request path

    browser
      -> Caddy (HTTPS, compression, static frontend files)
      -> Django (ASGI)
           middleware: request id (first), rate limit (last)
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
| Wiring | `core/wiring.py` | The composition root: one table per provider kind (`tomtom`, `open_meteo`, `fake`) mapping a name to a builder and its attribution; weather is wrapped in `CachingWeatherProvider`; providers are built once per process; `use_providers` swaps them in tests; `limits()` gives `PlanningLimits` from settings |
| Wiring | `core/provider_names.py` | The provider name enums the settings accept |
| HTTP | `core/middleware.py`, `core/request_context.py` | Request id (header and log filter); per-client rate limits by path scope, 429 catalog error |
| HTTP | `core/api.py`, `core/urls.py` | API router, version prefix, exception handler mapping named errors to the error catalog |
| HTTP | `core/readiness.py`, `core/schemas.py` | Readiness checks as a table (database, active rule set) |
| Boot | `core/serve.py` | Starts uvicorn from the validated settings |
| Checks | `tools/check_comments.py`, `frontend/scripts/check-comments.mjs` | Enforce the no-explanatory-comments rule |
| Entry | `planning/api/views.py` | Thin async views: validate, call one service, return a schema |
| Contract | `planning/api/schemas.py`, `trip_schemas.py`, `grid_schemas.py`, `place_schemas.py`, `inputs.py` | Request and response schemas, the source of the OpenAPI document; `inputs.py` converts `{value, unit}` to metric and times to UTC, once |
| Use cases | `planning/services/plan_trip.py` | Plan a trip (`trip-planning.md`) |
| Use cases | `planning/services/route_options.py` | Top up to 3 distinct routes |
| Use cases | `planning/services/weather_grid.py` | Build the heatmap grid |
| Use cases | `planning/services/places.py` | Place suggestions and details, passed through, never cached |
| Use cases | `planning/services/checks.py`, `limits.py`, `attribution.py`, `constants.py` | Shared local checks (departure range), the operator bounds, provider notices, fixed service constants |
| Domain | `planning/domain/values.py` | `Coordinate`, `RouteRequest`, `ProviderRoute`, `CellForecast`, `Place`, `TripOptions` and the other provider values |
| Domain | `planning/domain/geometry.py`, `detour.py` | Line measuring, simplification, polyline encoding, ferry intervals; detour via points |
| Domain | `planning/domain/checkpoints.py` | Checkpoint placement |
| Domain | `planning/domain/timeline.py` | Truck speed, rest stops, arrival times |
| Domain | `planning/domain/route_distinct.py` | Whether a route is distinct from those already kept |
| Domain | `planning/domain/risk.py` | Classification with bands and load rules |
| Domain | `planning/domain/weather_lookup.py` | Cell key and the forecast hour per variable |
| Domain | `planning/domain/stretches.py`, `summary.py`, `refine.py` | Stretch levels, per-route summaries, refine sampling |
| Domain | `planning/domain/ranking.py` | Ranking key and recommendation |
| Domain | `planning/domain/corridor.py`, `grid.py` | Grid cells around the routes; the classified heatmap grid |
| Domain | `planning/domain/options.py` | The trip option registry |
| Domain | `planning/domain/providers.py` | `RouteProvider`, `Geocoder`, `WeatherProvider` protocols |
| Adapters | `planning/adapters/tomtom/` | Routing and place search: `client.py`, `protocol.py` |
| Adapters | `planning/adapters/open_meteo/` | Forecasts: `client.py`, `protocol.py` |
| Adapters | `planning/adapters/forecast_cache.py` | Forecast cells in the Django cache |
| Adapters | `planning/adapters/http.py` | Shared client builder, rate limiter and retrier |
| Adapters | `planning/adapters/fake/` | Keyless, deterministic routes (3 bowed lines), places and patterned weather that meets every level; chosen with the `fake` provider names |
| Catalogs | `planning/constants.py`, `keys.py`, `text.py`, `events.py`, `errors.py` | One home per kind of value |
| Rules | `rulesets/domain/schema.py`, `validator.py`, `defaults.py` | Rule set types, the one validator, the seed values |
| Rules | `rulesets/models.py`, `admin.py`, `migrations/` | Versions in the database, admin screens, seed migration |
| Rules | `rulesets/services/active.py` | Returns the active `RuleSet` |
| Shared | `shared/units.py` | Exact unit conversion |
| Shared | `shared/risk_levels.py` | The risk level table |
| Shared | `shared/weather_variables.py` | The weather condition table |

`planning/domain/` and `rulesets/domain/` import nothing from Django, the HTTP client or any
adapter. `import-linter` enforces it (`[tool.importlinter]` in `backend/pyproject.toml`).

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
| Validated rule sets | Cache, one day | Version and creation time in the cache key |
| Rate limit counters | Cache, one minute | Scope, client and window in the key |
| Driver preferences | Browser `localStorage` | `schemaVersion` in the stored object |

Nothing is stored per driver on the server, and route results from a provider are never stored
(`trip-planning.md`).

## Decisions

Each significant choice has an ADR in `docs/adr/`.
