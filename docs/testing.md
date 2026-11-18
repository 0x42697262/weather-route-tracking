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
| `planning/domain/stretches.py` (ferries) | A ferry stretch with `ferry_level` null: counted as ferry distance, out of ranking and average, warning set; with `ferry_level` set: counted at that level; a checkpoint on a ferry keeps its forecast but no level |
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

- TomTom routing and place search, Open-Meteo: the request built (path, query, units), a recorded
  response parsed into domain objects in metric, a malformed response rejected, a timeout mapped to
  the named error, a retry on a retryable status.
- Recorded responses live under `tests/fixtures/` with keys removed. Routing fixtures are trimmed
  copies of real TomTom responses (a real response is 1 to 3.5 MB, F-47).
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

Built (`npm run verify` runs them with lint, the comment check and the type check):

| File | Covers |
|---|---|
| `trip-form/TripForm.test.tsx` | Missing places and load caught before any request; a server field error shown at its field (`aria-describedby`, `aria-invalid`); an error without fields as an alert; "Custom options in use" and its reset |
| `trip-form/draft.test.ts` | The request: load in the display unit, spacing as entered, departure now or picked; every missing field listed; dotted server paths mapped to fields; the departure window; custom options and the reset request |
| `routes/RouteList.test.tsx` | Cards in rank order with rank, label, time, distance and distance per level; a route warning with its distance; the fewer-than-3 notice; tapping selects |
| `routes/verdict.test.tsx` | The verdict in each state: nothing asked, loading, recommendation (with unknown distance), no recommendation, failure |
| `map/geojson.test.ts`, `map/layers.test.ts` | Stretch, checkpoint, truck and grid GeoJSON; bounds; level colors; heatmap paint read from feature state; stable layer ids |

Fixtures are typed with the generated schema (`src/test/fixtures.ts`). `src/test/setup.ts` replaces
`fetch` with a stub each test can program (`setFetchHandler`), so API errors run through the real
client and error parsing.

### End-to-end (`frontend/e2e/`, Playwright 1.65.1)

Run against the Compose stack with fake providers, then put the normal stack back:

    docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build
    cd frontend && npm run e2e
    cd .. && docker compose up -d --build

`docker-compose.e2e.yml` sets `ROUTE_PROVIDER`, `GEOCODER` and `WEATHER_PROVIDER` to `fake` and
raises the trip rate limit to 120 a minute. The base URL is `https://localhost` (`E2E_BASE_URL`
overrides it); HTTPS errors from Caddy's local certificate are ignored; the browser time zone is
America/Chicago. If the installed Chromium does not match Playwright's build, set
`E2E_CHROMIUM_PATH` to its executable (`facts.md` F-67).

| Spec | Checks |
|---|---|
| `plan-trip.spec.ts` | Pick Dallas and Oklahoma City from the suggestions, enter a load, find routes: 3 cards, the verdict names a route, the first card is recommended; the heatmap becomes ready; 6 slider steps change the hour label and the value text; the Wind layer can be chosen |
| `slider-performance.spec.ts` | On an emulated phone (390 x 844, scale 3, touch, CPU 4x slower), a long trip, dragging the slider from hour 0 to 48 makes no network request; frame rate and frame times are printed and attached (`frontend.md`, Time slider) |

Last run, 2026-11-17: both passed (about 25 s).

## Reference trips

Real trips used to check the app end to end, from well-mapped corridors to places with little
data. The first run (2026-11-17, `facts.md` F-46, F-54, F-55) gave the results below. Repeat them
after each step that changes routing, weather or ranking, and update this table when a result
changes.

### Well-mapped

| Trip | First result | What it shows |
|---|---|---|
| Dallas TX to Oklahoma City OK | 5 routes, 3 kept | The normal case |
| Dallas TX to Houston TX | 5 routes, 3 kept | The normal case |
| Chicago IL to Denver CO | 5 routes, 3 kept; crosses a time zone | Long trip, rest stops, a zone change in arrival times |
| Los Angeles CA to Las Vegas NV | 5 routes, 3 kept; one request took 10.3 s | Slow provider responses |
| Denver CO to Salt Lake City UT | 3 routes, 3 kept | Mountain passes, snow in winter |
| Seattle WA to Portland OR | 5 routes, 2 distinct; 3rd from the fallback (`slower`, 695 km, 2.3 times the fastest) | Top-up rounds, then the fallback |

### Sparse data

| Trip | First result | What it shows |
|---|---|---|
| Manila to Baguio, Benguet (Philippines) | 5 routes, 1 kept; alternatives over 2 times slower | Fewer than 3 routes after top-up; the notice |
| Tuguegarao, Cagayan to Legazpi, Albay (Philippines) | 5 routes, 3 kept; 1,113 km in 26.2 h; ferries | Very long and slow; ferries; rest rules outside the US |
| Davao City to Cotabato City (Philippines) | 5 routes, 3 kept | Typical provincial roads |
| Manila to Cebu City (Philippines) | 5 routes, 3 kept; 2 ferries; up to 14% of points without truck data | Island crossings by ferry |
| Ulaanbaatar to Khovd (Mongolia) | 5 routes, 3 kept; 1,543 km | Long, sparse roads |
| San Diego CA to Tijuana (Mexico) | 5 routes, 3 kept; 2 countries | A border crossing |

### No road route

| Trip | First result | What it shows |
|---|---|---|
| Basco, Batanes to Manila (Philippines) | HTTP 400, `NO_ROUTE_FOUND` | The "no road route" error, before any weather call |
| Nome AK to Anchorage AK | HTTP 400, `NO_ROUTE_FOUND` | The same, inside the US |

Recorded responses from these trips (keys removed, geometry trimmed) are the routing fixtures for
adapter and service tests.

## Checked by hand, recorded in the verification checklist

- Slider drag stays smooth on a real phone (frame rate from the browser performance panel); the emulated measurement is automated above.
- The layout at phone, tablet and desktop widths.
- The reference trips above against the live providers after each deploy.

## Left out of the first version

Cross-browser runs, visual regression tests, load tests, and end-to-end coverage beyond the one
main flow.

## Commands

One verify command per side (`engineering-guidelines.md` section 13). GitHub Actions runs both, and
the contract check, on every push and pull request. Pushed tags additionally build the release
container images.
