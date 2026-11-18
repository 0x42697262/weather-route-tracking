# Engineering guidelines

Rules for anyone (human or LLM) working in this repository. Backend: Python / Django. Frontend:
React with TypeScript.

Rules marked **(hard rule)** are non-negotiable; the rest is strong guidance. `AGENTS.md` wins over
this file if they ever disagree.

How to use this file:

1. Read `AGENTS.md` and `docs/SPEC.md` first.
2. Apply sections 1–5 always; the others when the task touches their area.
3. Run the checklist in section 14 before saying a task is done.

---

## 1. Working with the programmer

- **Act when you have enough information.** Ask only when a decision is genuinely theirs (scope, risk,
  cost, product behavior) and cannot be read from the code or a sensible default. Batch questions;
  put the recommended option first.
- **Discuss before building** when the programmer writes "discuss", or when a request hits a blocking
  technical constraint: state the constraint plainly, give the options with their costs, recommend
  one, and stop.
- **Say what you will do** in one or two sentences before starting; give a one-line update when a
  major phase starts or the plan changes.
- **Report faithfully:** what was done, what was verified and how, what was not, and what was left
  behind (files, remote state, created resources). Never claim a test passed that was not run. Mark
  unverified claims "UNVERIFIED".
- **Earlier answers are binding.** If the programmer answers "what I said earlier", find their earlier
  statement and apply exactly that; do not ask again.
- **Approval for a destructive action covers only the named target.** Never extend it to other
  targets or to a later context.
- **Never print secrets** (API keys, tokens, `.env` contents). Pass them through environment
  variables without echoing; keep them out of output, commits, docs and fixtures.
- **Commit only when asked**, one commit per logical change; do not push unless asked. No
  `Co-Authored-By` or other attribution lines.
- **Check the actual source or docs** of a library or third-party API before relying on a behavior,
  and record it as a confirmed fact (section 11).

---

## 2. Core idea

The application is a set of plain business rules surrounded by thin layers that talk to the outside
world (HTTP, database, cache, third-party APIs, the browser). Keep the rules independent of Django,
React and I/O, keep the boundaries thin and explicit, and let data flow one way:

    request -> view (entry) -> service -> domain rules (pure) -> adapters (APIs, cache, DB)

- Views receive input and validate it.
- Services orchestrate a use case and own transactions.
- Domain rules decide.
- Adapters talk to the outside world.

---

## 3. Layers

Each module has one job. Keep these layers apart.

| Layer | Job | May depend on | Must not |
|---|---|---|---|
| Entry (Django views / API endpoints, management commands) | Parse and validate input with a schema, call one service function, return a response schema | Services, schemas, text catalog | Contain business rules, query the ORM or call third-party APIs directly |
| Services / use cases | Run one use case end to end: load data, call rules, persist, own the transaction, order the checks (3.1) | Domain rules, adapters (through their interfaces) | Know about `HttpRequest`, status codes, or response shapes |
| Domain rules | Pure logic: classifications, thresholds, rankings, calculations, time arithmetic | Other domain modules, value objects, settings objects | Do I/O, read the clock or env, import `django.*`, `httpx` or any adapter |
| Adapters (clients, repositories) | Talk to third-party APIs, the cache and the DB. Translate to and from plain domain objects | `httpx`, the Django ORM, the Django cache | Make business decisions |
| Protocol helpers (inside an adapter) | Pure functions that build request params and parse responses of one external API | Keys/constants | Do I/O |
| Config | Typed, validated settings loaded once at boot | Environment | Be read ad hoc with `os.environ` / `import.meta.env` deep in the code |
| Text | Every user-facing string, error message and log event name | Nothing | Be inlined in logic |
| Frontend | Presentation and interaction | The API contract | Be the authority on any computed business value (section 8) |

Rules of thumb:

- **Thin entry points.** A view is about 5 to 15 lines: validate, call a service, return a schema.
- **Pure domain rules.** Pass `now`, IDs and settings in as arguments. No `datetime.now()`,
  `timezone.now()` or `Date.now()` inside domain code.
- **Adapters hide vendors.** Services depend on a `Protocol` (`WeatherProvider`, `RouteProvider`,
  `Geocoder`), not on the vendor's response format. Swapping a vendor touches one adapter. A client
  takes its transport as a parameter (`httpx.AsyncClient(transport=...)`), so tests pass
  `httpx.MockTransport` instead of patching modules.
- **One wiring place.** A single composition module (e.g. `<project>/wiring.py`) builds the adapters
  and services from settings; views get services from it. Nothing else instantiates infrastructure.
  Tests replace it through fixtures, never with `unittest.mock.patch` on modules.
- **Small pure functions, frozen lookup tables** (`MappingProxyType`, tuples, frozen dataclasses,
  `as const` objects in TS) and dispatch maps instead of long `if` chains.
- **Typed boundaries:** frozen dataclasses (`@dataclass(frozen=True, slots=True)`) or pydantic
  models for data that crosses modules; `Readonly<...>` types in TS. Parse untrusted input once at
  the boundary.
- **Errors are small named classes** (`class UpstreamUnavailable(Exception): ...`), one per failure
  family; one exception handler maps each to an error code, a message from the catalog and an HTTP
  status. Unexpected errors are re-raised, never swallowed.

### 3.1 Order of checks in a use case

Cheap and local first, remote last:

1. input validation (400-class errors);
2. rules decidable locally (ranges, limits, dates in the allowed window);
3. **before any outbound request**, reject anything that would make the remote calls pointless;
4. remote calls (geocoding, routing, weather), bounded and with timeouts (7.1);
5. pure domain computation on the results;
6. persistence or caching of derived results, if any.

---

## 4. Hard rules

### 4.1 No explanatory comments in code (hard rule)

Code explains *what* it does through names, small functions and small types. The *why* (business
reasons, constraints, rejected alternatives, third-party quirks) goes in `docs/` (one file per topic)
or an ADR. Comments rot; docs get reviewed.

- Python docstrings are allowed on modules, classes and functions. They describe the contract
  (purpose, arguments, return value, raised errors); long "why" explanations still go in `docs/`.
- Inline `#` comments and `//` / `/* */` comments are not allowed.
- Allowed exceptions: lint-disable directives (`# noqa: RULE`, `// eslint-disable-next-line rule`)
  whose reason is in the docs, `# type: ignore[code]` with the reason in the docs, license headers.

### 4.2 No magic values (hard rule)

Every number, duration, limit, threshold, status, route name, cache key and string lives in exactly
one named place:

| Kind | Where |
|---|---|
| Values an operator may tune per environment (timeouts, concurrency, cache TTLs, rate limits, feature flags) | Typed settings (section 4.3), sourced from env, with defaults |
| Business thresholds and rules | The active rule set (4.7.1); the seed defaults live in one frozen defaults module |
| Fixed internal constants (retry counts, page sizes, schema versions, unit conversion factors) | A `constants` module per area |
| Statuses, levels, kinds | Enums: `enum.StrEnum` / `enum.IntEnum` (ordered levels), Django `TextChoices` only in models; TS union types or `as const` objects |
| User-facing text | Frontend `text/` module; backend `text.py` per area |
| Error codes and messages returned by the API | One error catalog (`ErrorCode` enum + messages), mirrored as a TS type through the contract (section 8) |
| Log event names | An `events` module per area |
| Cache keys, URL builders, query param names, env var names, regexes, DOM ids | One `keys` module per area |

Plain `0`, `1`, `None`/`null`, `True`/`true` and `""` are fine where obvious. Name `-1`.
Parameterized messages are functions in the catalog (`def route_not_found(origin: str) -> str`).
**Units go in names** (`wind_speed_kmh`, `distance_km`, `snowfall_cm_per_h`, `load_kg`) or in value
types. **The server computes in metric only** (km, km/h, mm/h, cm/h, kg, seconds, UTC). Values in
any other unit are converted exactly once: provider responses in the adapter, rule set thresholds
when the rule set is loaded, customer input at the API boundary. Domain code never converts. The
frontend converts for display only (4.7.2).

Enforcement: Ruff `PLR2004` (magic-value-comparison); ESLint `no-magic-numbers` with the obvious
values ignored.

### 4.3 Config is validated at boot (hard rule)

- Backend: one settings schema (`pydantic-settings` `BaseSettings`) in one module, instantiated once
  from `settings.py`. Missing or invalid values fail startup with a clear message. Everything else
  reads the typed, immutable settings object (or `django.conf.settings`), never `os.environ` /
  `os.getenv`. Enforce with Ruff `flake8-tidy-imports.banned-api` on `os.environ` and `os.getenv`,
  ignored only for the settings module.
- Frontend: `import.meta.env` is read in one module (`src/config/`), validated with a schema (Zod) at
  startup, exported as a frozen object. Only `VITE_`-prefixed variables reach the browser and **all
  of them are public**; no secrets in the frontend, ever. Keyed third-party APIs are called through
  the backend.
- Derived settings resolve once in the settings module.
- A cap or interval of 0 conventionally means "off" or "no limit"; document it where used.

### 4.4 Everything that persists is versioned (hard rule)

- **Database:** schema changes only through Django migrations. Never edit an applied migration. Use
  expand-and-contract for breaking changes.
- **API:** versioned path (`/api/v1/...`). Additive changes are fine; breaking changes get a new
  version or a new field.
- **Cached payloads and stored JSON:** carry a schema version, in the payload (`"schema_version": 1`)
  or in the cache key. Readers accept old versions or treat them as a miss; unknown newer or
  malformed data is a clear error.
- **Frontend persisted state** (`localStorage`): versioned; on unknown or malformed data, discard and
  fall back to defaults.

### 4.5 Feature flags (hard rule for risky or unfinished behavior)

- Optional, risky or unfinished behavior sits behind a named flag in typed settings, off by default
  where the programmer says so.
- Each flag has an **owner and a removal date**, recorded where the flag is documented.
- Unfinished features the programmer wants visible are shown **disabled with a hint** ("Coming
  soon"), never as client-only behavior that pretends to work (section 8).

### 4.6 No relative imports (hard rule)

- **Python:** absolute imports only (`from <app>.domain.thresholds import WIND_BANDS`, never
  `from .thresholds import ...`). Enforce with Ruff `TID252` and
  `[tool.ruff.lint.flake8-tidy-imports] ban-relative-imports = "all"`.
- **TypeScript:** imports go through the `@/` alias mapped to `src/` (`tsconfig.json` `paths` +
  the Vite `resolve.alias`), never `./` or `../`. This includes CSS and asset imports. Enforce with
  ESLint `no-restricted-imports` patterns `["./*", "../*"]`.

### 4.7 Configurability (hard rule)

The app is built to become a product: values that owners or operators could reasonably want
different are configurable, not hard-coded. Business rules are configured by **staff** (owners,
admins), never by customers. There are four tiers, each with one home:

| Tier | Who changes it | Examples | Where it lives | Where it is validated |
|---|---|---|---|---|
| Operator settings | Whoever deploys | Timeouts, concurrency, cache TTLs, rate limits, provider URLs, feature flags, admin URL | Env -> typed settings (4.3) | Server, at boot |
| Business rules | Staff, in Django admin | Weather thresholds, conditions, load rules, risk levels' numeric scale, ranking order, allowed checkpoint spacings, number of routes, forecast window | A versioned **rule set** in the database (4.7.1) | Server, on save and on load |
| Trip parameters | The customer, per trip | Checkpoint spacing (from the values the active rule set allows) | The **option registry** on the server; values sent with each request | Server, on every request |
| Display preferences | The customer | Units (imperial/metric), theme, map style, layer visibility | Frontend only (versioned `localStorage`, 4.4) | Frontend, on load |

#### 4.7.1 Business rules (rule sets)

- **Rules are data, not code.** A rule set holds per-condition bands and compound rules (e.g. wind
  band + load over a weight -> level). The domain evaluates the data; nothing is ever `eval`ed.
- **The five risk levels are fixed** (Low, Moderate, High, Severe, No Travel). Staff move the
  cutoffs and add rules; they cannot add, remove or rename levels, because ranking depends on them.
- **Conditions come from a fixed catalog** (`WeatherVariable` enum) of fields the weather provider
  actually returns, each with a canonical unit. Staff may enter a threshold in any supported unit
  (`{"value": 80, "unit": "km/h"}`); it is stored as entered and converted once to the canonical
  unit for evaluation. The weather adapter fetches only the variables the active rule set uses.
- **One pure validator** (`validate_rule_set(data) -> RuleSet`, raising a named error with every
  problem) is used by the admin form (`Model.clean()`), the seed migration and the load path. It
  checks: bands ascending with no gaps or overlaps, known variables and units, levels valid, rule
  count under a cap, `schema_version` known (4.4).
- **Versioned and immutable.** Publishing creates a new version; a published version is read-only.
  Exactly one version is active (database constraint). Rollback means activating an earlier version.
- **Seeded, never empty.** A data migration creates version 1 from the defaults in `docs/SPEC.md`
  (kept as a frozen defaults module). The readiness check fails if no rule set is active.
- **Audited.** Each version records who created and who activated it, and when (plus Django's admin
  log).
- **Results echo `rule_set_version`**, so every result can be traced to the rules that produced it.
- **Caching:** raw forecasts are cached per grid cell and hour, independent of rules. Computed
  plans are not cached. Activating a version needs no cache flush.
- **Admin access:** staff accounts only; the admin path comes from settings (`ADMIN_URL`), HTTPS
  only, never linked from the customer UI. Requires a database: PostgreSQL in production, SQLite is
  acceptable locally.

#### 4.7.2 Trip parameters and display preferences

- **One option registry on the server** (e.g. `<app>/domain/options.py`): for every trip
  parameter, its name, type, default, bounds (min, max, step or allowed values), canonical unit, tier
  (`basic` / `advanced`) and text key. Defaults and allowed values come from the active rule set.
- **The frontend never hard-codes defaults or bounds.** It reads them from the registry endpoint
  (`GET /api/v1/options`) or from the generated contract, and renders the form from that.
- **The server validates every parameter against the registry** and rejects out-of-range values with
  a catalog error (no silent clamping). Omitted parameters take the default, so a request with no
  options at all is valid.
- **Domain rules take the resolved options as one immutable object** (`TripOptions`); they never read
  defaults themselves.
- **Responses echo the effective options** (`options_used`) next to `rule_set_version`, so the UI labels results correctly and a
  result can be reproduced.
- **Cache keys include every option that changes the result** (a stable hash of the resolved
  options), never options that don't.
- **Display preferences never change computation.** Unit conversion for display happens in the
  frontend from the canonical units the API returns.
- **Every option costs a test matrix and a support burden.** Add one only with a real use; list it in
  `docs/SPEC.md` first.

---

## 5. Code style

- **No single-letter names**, loop counters included (`index`, `checkpoint`, `entry`); `_` only for
  ignored values. ESLint `id-length` (min 2, `_` excepted); review for Python.
- **Match the surrounding code:** naming, idioms, file layout. Read neighbors before writing.
- **American English** in code, UI copy and docs.
- **Python:** 3.14 with Django 6.1 (Django 6.1 needs Python 3.12 or newer). Full type hints on every
  function. Format and lint with Ruff; type-check with mypy (`django-stubs`) or pyright in strict mode.
- **TypeScript:** `strict: true`, no `any` (ESLint `@typescript-eslint/no-explicit-any`), no
  non-null assertions on untrusted data.
- **Time:** timezone-aware datetimes only (`USE_TZ = True`); UTC inside the backend and in the API;
  convert to local time only for display. Never compare naive and aware datetimes.
- **Simplicity:** the smallest design that works; no speculative abstraction; no interface with one
  implementation "for later" except at true vendor boundaries (routing, geocoding and weather
  providers count). One module, one job; small functions with intention-revealing names.

---

## 6. Request and lifecycle model

- **Request lifecycle:** middleware (request ID, rate limit, CORS) -> schema validation -> view ->
  service -> response schema.
- **Outbound fan-out** (many checkpoints, several routes) runs concurrently with `asyncio` and an
  async `httpx.AsyncClient`, bounded by a semaphore whose size is a setting. Async views end to end;
  no sync ORM calls inside async code without `sync_to_async`.
- **Background jobs** only when a request cannot finish within its time budget. If introduced: each
  job is idempotent, has a timeout, a retry policy and a failed-jobs path. Record the decision in an
  ADR first.

---

## 7. Reliability, scalability, maintainability

### 7.1 Reliability: fail safe and recover

- **Validate at every boundary** (request body, query params, every third-party response). Trust
  nothing from the client or a third party; parse vendor responses into typed objects and reject
  missing or out-of-range fields.
- **Timeouts on every outbound call** (`httpx.Timeout` from settings). No call waits forever.
- **Retries with exponential backoff, jitter and a cap**, only for idempotent reads (all current
  third-party calls are GETs). Never retry a 4xx other than 429; honor `Retry-After`.
- **Graceful degradation:** if a non-critical dependency fails (e.g. the heatmap layer), serve the
  core result (routes and risk) and say what is missing. If a critical input is missing for a
  checkpoint, mark it "unknown" explicitly; never default to Low.
- **Clean shutdown:** close HTTP clients (`async with` / app lifespan).

### 7.2 Scalability: bounded work

- **Bound every input:** max distance, max checkpoints per route, max routes, forecast window. Values
  in settings or constants.
- **Batch and dedupe outbound calls:** group checkpoints per request where the vendor allows it, round
  coordinates and times to the vendor's resolution, and fetch each unique (cell, hour) once.
- **Cache read-heavy data** (forecasts per grid cell and hour) through the Django cache with keys
  from `keys.py`, explicit TTLs and a version (4.4). Never cache the only copy of anything.
- **Check a provider's terms before caching or storing its results**, and record the finding in
  `docs/facts.md`. Route results and place suggestions are not cached (F-8, F-9).
- **Stateless app servers:** no per-user state in process memory; anything shared goes in the cache
  or DB.
- **Rate limit** public endpoints, and throttle our own calls to third parties to stay under their
  published limits (record the limits as confirmed facts).
- **Bound every query** if a DB is used: no unbounded `.all()`; `select_related` / `prefetch_related`
  to avoid N+1.

### 7.3 Maintainability

**Operability**
- Structured JSON logs (stdlib `logging` with a JSON formatter, or `structlog`) with a request ID and
  an event name from the `events` module.
- Log decisions with their inputs ("checkpoint classified: wind_kmh=61.2 load_kg=19051 level=SEVERE
  rule=load_wind"), so one line explains a result. Never log API keys or full upstream URLs that
  carry keys.
- A health endpoint (`/api/health`) and a readiness check that does not call third parties.
- `DEBUG = False` and the browsable/debug tooling off in production.

**Evolvability**
- New variants (risk conditions, sampling intervals, providers) are added through data, enums and
  dispatch tables, not new `if` chains.
- Domain rules take settings/threshold objects, so new knobs don't change call sites.
- **Never branch on one specific member of a set** (`if level == SEVERE`, `if variable == "wind"`,
  `if provider == "tomtom"`). Give the set a table with the properties code needs (order, flags,
  units, text key, color token) and iterate over it. Adding a member is then one table row.
  `docs/extensibility.md` lists the sets this applies to.
- Anything the frontend must list (levels, conditions, heatmap layers, spacings, units) comes from
  the server and is rendered by iterating. The frontend adds only what is purely visual for a new
  member (a color token, a label).
- Reuse small value objects (`Coordinate`, `Distance`, `Speed`, `TimeWindow`) across features.

### 7.4 One source of truth

- Third-party APIs are the source of truth for routes and forecasts; the backend is the source of
  truth for every derived value (risk levels, ranking, summaries).
- Caches are derived; each has one documented way to rebuild it (expire or bump the version).

---

## 8. Client/server contract

- **The server is authoritative.** Risk classification, load rules, mileage per level, averages,
  ranking and the recommendation are computed on the server. The frontend displays them; it never
  re-implements a threshold or a ranking rule.
- **Typed contract, defined once:** request/response schemas live on the backend (Django Ninja
  pydantic schemas, or DRF serializers with `drf-spectacular`), exported as OpenAPI, and the
  frontend's types are generated from it (`openapi-typescript`). No hand-written duplicate types for
  API payloads. Regenerate in the same commit as the schema change.
- **Validate on the server**; on the client, check the generated types at compile time and parse
  responses at the API boundary where shape drift would break the UI.
- **Audit for mismatches:** for each value the UI shows, know whether it comes from the server or is
  computed locally, and from which inputs. Local computation is limited to presentation (formatting,
  colors, map geometry).
- **Remove features the server can't back.** A disabled "Coming soon" item is fine (4.5).

---

## 9. Secrets

- Secrets only in env or the host's secret manager, never in the repo. `.env` is gitignored;
  `.env.example` lists every key with a placeholder.
- Third-party API keys live only on the backend (4.3). The frontend calls our API, not keyed vendors.
- Map tile or other browser-side keys that must be public are restricted by origin at the vendor and
  documented as public.
- CORS: an exact allow-list from settings; no `*` in production.

---

## 10. UI and UX

### 10.1 Design (Apple design philosophy)

- **Mobile-first.** The primary devices are phones and tablets in a truck cab. Design and check
  every view at phone width first; larger screens adapt from that. Touch targets are at least
  44 px, and nothing depends on hover.
- **Glanceable.** The verdict (which route, how risky, how long) is readable in one look without
  opening anything. Detail is one tap away, never required.
- **Clarity, deference, depth:** the map and the recommendation first; controls recede; one obvious
  primary action per view.
- **Sheets/popovers** for short tasks; Escape closes, Enter triggers the primary button, focus returns
  to the opener.
- **Plain language**, sentence case, verbs on buttons ("Find routes"); an ellipsis when an item opens
  a further step.
- Sensible defaults (e.g. departure = now, a default sampling interval). The app is fully usable
  without opening any settings.
- **Progressive disclosure for configuration (4.7):** the main form shows only the essential inputs
  and `basic` options. `advanced` options sit behind a collapsed "Advanced options" disclosure,
  closed by default. Each advanced option shows its default and unit, with a one-line hint.
- When any trip option differs from its default, say so near the results ("Custom options in use")
  and offer **Reset to defaults**. Users are never surprised by a setting they forgot they changed.
- Unavailable features: visible but **disabled** with a one-line hint.
- Status feedback (loading, partial data, errors) in an unobtrusive status line; warnings do not
  block.
- Risk levels are never shown by color alone: color + label/icon, with a legend. Palette checked for
  color-blind contrast.
- Colors only through tokens. The first version ships the light theme only; a dark theme is a
  token set added later (`docs/adr/0008-light-theme-only.md`). Keyboard access and ARIA roles on custom
  controls (the forecast slider is a real `input type="range"` or has `role="slider"` with
  `aria-valuenow`/`aria-valuetext`).
- All UI strings in `src/text/`; element ids in `keys`.
- **Use maintained libraries for UI primitives** (sheet/drawer, slider, popover, dialog, map
  bindings) instead of hand-writing them. Record each choice in `docs/frontend.md`.

### 10.2 State and rendering performance

- **Server state** goes through TanStack Query, keyed by API resource and parameters. **UI state**
  (selected route, slider hour, panel open) stays in component state or a small store. Never copy
  server data into local state.
- **Map layers are created once** and updated by swapping their data source; never re-create the map
  or a layer on re-render or slider change.
- **Slider changes do not fetch.** Load the whole 0–48 h forecast grid once per trip, then each
  slider step only selects a precomputed frame. Throttle slider-driven updates to animation frames
  (`requestAnimationFrame`).
- **Memoize derived geometry** (GeoJSON for routes, checkpoints, heatmap frames) with `useMemo`
  keyed on the server data, not on unrelated props.
- **Prefer GPU-rendered layers** (WebGL heatmap/circle layers) over one DOM marker per checkpoint.
- Check performance with the React Profiler and the browser Performance panel; target 60 fps while
  dragging the slider and record the measurement in the verification checklist.

---

## 11. Documentation as the design record

- `README.md`: what it is, setup, run, test, deploy; a short section per user-facing feature.
- `docs/README.md`: table of contents, one line per doc.
- `docs/<topic>.md`: how a feature actually works: the flow, the numbers, the edge cases, the log
  event names to look for, the rejected alternatives, and "why X is not possible" when a limitation
  exists.
- `docs/architecture.md`: the module map as a table (stage → code → notes).
- `docs/adr/NNNN-title.md`: one short ADR per significant decision (context, decision,
  consequences): provider choices, map library, contract tooling, hosting.
- `AGENTS.md`:
  - conventions and working rules (short);
  - **confirmed facts** about third-party APIs and frameworks (units, limits, resolution, quirks),
    each with where it was verified. When they grow past a handful, move them to `docs/facts.md`
    (ID, fact, source, consequence) and link it. Facts come from primary sources (vendor docs, live
    responses, library source), not community lore;
  - **verification checklist:** one concrete check per behavior change (what to do, and the
    response, log line or UI result to expect).
- **Docs, ADRs and checklist entries are updated in the same change as the code, in their own
  commits.**

---

## 12. Testing

- **Domain rules:** fast `pytest` unit tests, many cases, no mocks (they are pure). Every threshold
  boundary gets a test on both sides of the edge (`pytest.mark.parametrize` tables).
- **Services:** tests with fake adapters (in-memory providers implementing the same `Protocol`) and
  a fixed clock, run through the real service function.
- **Adapters:** `httpx.MockTransport` with recorded vendor responses (fixtures sanitized of keys) that
  check method, path and query; parse failures and timeouts covered. Live vendor tests are opt-in,
  marked (`@pytest.mark.live`) and skipped by default.
- **API:** endpoint tests with `pytest-django` and the Django test client, including validation
  failures and upstream failures mapped to the error catalog.
- **Frontend:** Vitest + Testing Library for component logic; a few Playwright end-to-end tests for
  the critical flow (enter trip → routes shown → recommendation visible → slider moves heatmap),
  run against a backend with fake providers.
- Cover: success, invalid input caught before any outbound request (assert the fake transport saw no
  request), upstream errors and timeouts, partial data, boundary values.
- **A bug fix starts with a failing test that reproduces it.** If the bug cannot be reproduced, say
  so with the scenarios tried and the untested hypotheses, ask for exact steps, and do not ship a
  speculative fix.
- Local-only scripts stay out of version control (a gitignored `scripts/local/`).

---

## 13. Repository layout

    backend/
      pyproject.toml               deps (uv), Ruff, mypy/pyright, pytest config
      manage.py
      <project>/                   Django project package
        settings.py                Django settings, built from the typed env settings only
        env.py                     pydantic-settings schema: the only place env is read
        wiring.py                  composition root: build adapters + services from settings
        urls.py  asgi.py
        api.py                     API router, exception handler -> error catalog
      <app>/                       one Django app per area
        api/
          views.py                 thin: validate -> service -> schema
          schemas.py               request/response schemas (the contract)
        services/                  use cases, ordered checks (3.1)
        domain/                    pure rules, value objects, enums, thresholds (no django imports)
        adapters/
          <provider>/
            client.py              async httpx client, transport injected
            protocol.py            pure request building / response parsing
        constants.py keys.py text.py events.py errors.py
        models.py                  thin: rule set versions, other persistence
        admin.py                   Django admin registration; forms call the domain validator
        migrations/
        tests/                     unit (domain), services, adapters, api
    frontend/
      package.json  tsconfig.json  vite.config.ts  eslint.config.js
      src/
        api/                       generated OpenAPI types + typed client
        features/<feature>/        components, hooks, state per feature
        components/                shared presentational components
        config/                    validated public runtime config
        text/                      UI strings
        keys.ts constants.ts
      e2e/                         Playwright tests
    docs/  docs/adr/  README.md  AGENTS.md  .env.example

- **One verify command** per side. GitHub Actions runs both on every push and pull request.
  Release builds (container images) run only on pushed tags. Run the verify commands locally before
  saying "done":
  - backend: `ruff check`, `ruff format --check`, the type checker, `pytest`;
  - frontend: `eslint --max-warnings 0`, `tsc --noEmit`, `vitest run`;
  - a contract check that the generated API types are up to date.

---

## 14. Before saying "done"

- [ ] `AGENTS.md` and `docs/SPEC.md` read and followed.
- [ ] Lint (zero warnings), type check and tests pass on both sides; output checked.
- [ ] Views thin; domain rules pure (no `django`/`httpx` imports, no clock reads); adapters hide
      vendors; one wiring place.
- [ ] No explanatory comments (docstrings allowed), no magic values, units in names, strings in their
      catalogs, no single-letter names, no relative imports.
- [ ] Config validated at boot; no raw env reads elsewhere; no secrets in the frontend.
- [ ] Persisted and cached data versioned; migrations for schema changes.
- [ ] Outbound calls bounded, batched, cached, with timeouts; retries only on idempotent reads.
- [ ] Server computes every business value; the UI only displays it; API types regenerated.
- [ ] Map/slider changes do not refetch or rebuild layers; performance checked.
- [ ] Optional/risky behavior behind a flag with owner and removal date.
- [ ] Tunable values are in the right tier (4.7); business rules come from the active rule set,
      validated by the one validator; responses echo `rule_set_version` and `options_used`.
- [ ] Docs, ADRs, confirmed facts and the verification checklist updated, in their own commits.
- [ ] Bug fixes start from a failing test (or the report says why no repro exists).
- [ ] No secrets printed, committed, logged or written into fixtures.
- [ ] Unverified claims marked as such.
- [ ] Commits only if asked; one per logical change; no attribution lines.
