# Trip planning

How a trip request becomes routes, checkpoints, arrival times, weather and a recommendation, and
how the heatmap grid is produced. Risk classification and ranking are in `risk-model.md`.

Items marked UNVERIFIED depend on provider behavior listed in `facts.md` and must be checked before
the code relies on them.

## Planning a trip (`POST /api/v1/trips`)

Input: origin and destination as coordinates plus the label the driver picked, departure time
(UTC), load weight, checkpoint spacing. Weight and spacing arrive as value plus unit and are
converted to metric at the API boundary.

Order of work in the service (`planning/services/plan_trip.py`), cheap checks first:

1. **Schema validation** of the request.
2. **Local rules**, before any outbound call: the spacing is one the active rule set allows; the
   load is within bounds; the departure is not in the past beyond a tolerance and not beyond the
   forecast range; origin and destination differ.
3. **Routes:** ask the route provider for alternatives, then top up to 3 distinct routes (below).
   Zero routes is a catalog error. Fewer than 3 after topping up is a normal result, flagged in
   the response.
4. **Checkpoints and arrival times** per route (pure, below).
5. **Weather:** one deduplicated lookup for every checkpoint of every route (below).
6. **Classify, build stretches, summarize, rank, recommend** (pure, `risk-model.md`).
7. **Return the result.** The plan is not stored on the server.

The response carries: the routes (geometry, distance, drive time, checkpoints, stretches, summary),
the ranking order, the recommendation or the reason there is none, `options_used`,
`rule_set_version`, `routes_requested` and `routes_found`.

### Reaching 3 routes

The target is 3 distinct routes. One Mapbox request returns at most 2 (`facts.md` F-5), and an
alternative "does not exist in all circumstances". The public OSRM server returned 1 and 2 on two
test trips (F-1). With Mapbox, at least one top-up round is therefore expected on almost every trip.

The service (`planning/services/route_options.py`) asks in rounds and stops as soon as it holds 3:

| Round | Request | Label on the route card |
|---|---|---|
| 1 | Fastest route with the provider's own alternatives | "Fastest", "Alternative" |
| 2 | Avoid toll roads | "Avoids tolls" |
| 3 | Avoid highways | "Avoids highways" |
| 4 | Through a detour point: a point pushed sideways from the middle of the fastest route, one side and then the other | "Detour" |

- Each adapter declares which rounds it supports; unsupported rounds are skipped. Mapbox supports
  avoiding tolls and highways through `exclude` (F-25).
- **Distinct (pure, `planning/domain/route_distinct.py`):** a new route is kept only if the share
  of its length that runs along an already kept route is under a limit, and its drive time is
  within a limit of the fastest route's. Both limits are constants. This drops repeats and
  detours no driver would take.
- A cap on extra requests per trip (setting) bounds the cost.
- Each kept route records how it was found. The fastest route is always first.
- If the rounds are exhausted with fewer than 3, the response says how many were found.

### Checkpoints (pure)

- Walk the route's line, adding up great-circle distance between points.
- Put a checkpoint at distance 0 (origin), then at every multiple of the spacing, then at the
  destination. If the last multiple falls within a minimum gap of the destination (constant), it is
  dropped so the final stretch is not a sliver.
- A checkpoint's position is interpolated on the line segment it falls in.
- A hard cap on checkpoints per route (setting) rejects requests that would exceed it, with an
  error that suggests a wider spacing.

### Truck speed and arrival times (pure)

Routing providers return car drive times (`facts.md` F-3). A truck is slower, so the app derives
truck time from the car time per segment of the route line:

    truck_speed = min(car_speed × truck_speed_factor, truck_max_speed)
    truck_time  = segment_distance ÷ truck_speed

- `car_speed` comes from the provider's per-segment distance and duration (F-6). If a provider
  gives only a total, the route is treated as one segment at its average speed.
- **`truck_speed_factor`** scales every segment. Default 1.0, which leaves car speed unchanged.
- **`truck_max_speed`** caps fast segments only. Default 65 mph. It models speed limiters and lower
  truck limits: fleets set limiters "most often at speeds from 60 to 70 mph" (F-13), and a routing
  engine's own truck example uses 10% slower with a 100 km/h cap (F-15). It may be empty, meaning
  no cap.
- Both live in the rule set, so staff change them in admin and the server supplies the defaults.
- A cap is used alongside the factor because one factor is wrong in both directions: it slows city
  streets where trucks keep pace with cars, and under-slows 75 to 80 mph interstates.
- What this does not capture: lower truck limits that apply in only some states (F-12), grades,
  and truck-restricted roads. Those need a provider with truck routing (F-11).

`arrival = departure + truck driving time to the checkpoint + rest time taken before it`.

All times are timezone-aware UTC. `now` is passed into the service by the view; domain code never
reads the clock. The client converts the departure from the device's time zone to UTC before
sending, and converts every returned time back for display (`frontend.md`).

### Rest stops (pure)

Long trips cannot be driven without stopping, and every stop shifts the weather the truck meets
later. Arrival times therefore come from one function, `build_timeline`, that returns elapsed time
and the stops it inserted.

**Method: a driving-and-rest clock.** Walk the route's segments in order, keeping three counters:
driving time since the last break, driving time in this shift, and time since the shift began.

| When this limit is reached | Insert | Then reset | Default from |
|---|---|---|---|
| 8 hours of driving since the last break | A 30-minute break | Driving since last break | F-19 |
| 11 hours of driving in the shift, or 14 hours since the shift began | 10 hours off duty | All three counters | F-16, F-17, F-18 |

- A segment that crosses a limit is split at the point where the limit is reached, and the stop is
  placed there.
- Breaks count toward the 14-hour window. Off-duty time starts a new shift.
- Stops add to elapsed time, so they move every later arrival time and are part of a route's
  travel time in the ranking.
- A stopped truck is not rated: risk applies to driving. On the slider, the truck marker stays at
  the stop for its duration, and each stop is listed in the route details.
- All five numbers and an on/off switch are rule set fields (`rest_rules`), so staff can match a
  fleet's policy or another country's rules.

**When the truck does not stop.** Some trips keep moving: two drivers taking turns, or a driver who
plans their own stops. Whether to add rest is therefore a **trip option** (`include_rest_stops`,
under Advanced options), not only a staff setting. Its default is the rule set's switch.

- Off: `build_timeline` inserts nothing, arrival is driving time only, and the weather is read for
  those earlier times.
- On, short trip: under 8 hours of driving no limit is reached, so nothing is inserted and the
  result is identical to off.
- The response says which was used (`options_used`) and how much rest was added per route, so a
  driver can see why an arrival time is later than the driving time.
- The app estimates; it does not enforce or check legal driving hours.

Assumptions, stated in the UI where rest is shown: the driver starts rested at departure; there is
no on-duty time that is not driving (loading, fueling); the 60 and 70 hour weekly limits (F-20) and
the adverse-conditions extension (F-21) are not modeled.

**Methods considered**

| Method | What it does | Why not now |
|---|---|---|
| No rest | Arrival is driving time only | Wrong for any trip over 8 hours of driving |
| Driving-and-rest clock | Above | Chosen: deterministic, pure, a few dozen lines, and matches the regulation's own structure |
| Clock plus real stopping places | Moves each stop to the nearest truck stop or rest area before the limit | Needs a places data source; the clock stays the same, only the stop position changes |
| Wait out the weather | Tries later departure times or longer stops and keeps the plan with the lowest risk | A search over departure and stop times that re-reads the forecast per candidate. Valuable, and a natural next feature: it reuses `build_timeline` and the classifier unchanged |

### Weather lookup

- Forecasts are hourly on a provider grid. A checkpoint's lookup key is (grid cell, forecast hour):
  the position rounded to the provider's grid resolution, and the forecast hour below.
- **Which hour to read** depends on how the provider reports the variable (`facts.md` F-27). The
  weather variable table records it per variable:
  - instant values (wind speed): the hour nearest the arrival time;
  - sums over the preceding hour (rain, snowfall): the first hour at or after the arrival time,
    because that hour's value covers the moment of arrival.
- Rain rate is `rain` plus `showers`. `precipitation` is not used because it includes snow.
- Keys are deduplicated across all routes, read from the cache in one `get_many`, and only the
  misses are fetched, in batched multi-location requests (UNVERIFIED batch size and limits),
  concurrently under a semaphore.
- A fetched cell is cached for its whole forecast range, so the heatmap and later trips reuse it.
- **Quota decides the cell budget.** Each location in a request costs at least one provider call,
  so batching saves round trips but not quota (F-30). The free tier allows 10,000 calls a day
  (F-31). The maximum cells per trip (checkpoints plus heatmap) is a setting sized from that
  quota, and a provider call counter is logged per trip.
- A checkpoint whose hour is outside the forecast range, or whose cell failed to load after
  retries, has no weather and its level is Unknown.

### No stored plans

The server keeps no copy of a plan. A routing provider's terms can forbid caching or storing route
results (Mapbox does, `facts.md` F-8), and a design that never stores them works under any
provider's terms. Forecast cells are cached; they come from the weather provider, whose terms are
checked separately (V-9).

## Heatmap grid (`POST /api/v1/weather-grid`)

Separate from planning so routes and the recommendation appear first.

1. Read the request: the route lines the client already holds (encoded), the departure time and
   the load. The lines are untrusted input: their count, point count and total length are checked
   against the same caps as a plan.
2. **Corridor (pure):** grid cells within a buffer distance of any route. Cell size starts at the
   provider's resolution and grows until the cell count is under a cap, so long trips stay bounded.
3. **Forecast** for every cell for each hour from departure to departure plus 48 hours, through the
   same cache as above.
4. **Classify (pure)** every cell and hour with the driver's load, using the same function as
   checkpoints.
5. Return, per cell: its center, and arrays with one entry per hour: the value and the level for
   wind, rain and snow (metric), and the combined level. Hours with no forecast are `null`. The
   client colors every layer from the levels, so it holds no thresholds.

The whole 48 hours go out in one response. Moving the slider never calls the server.

## Other endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/options` | What the driver may choose and the defaults, from the active rule set; `rule_set_version` |
| `GET /api/v1/places?query=` | Place suggestions for the origin and destination fields, through the geocoder adapter so the key stays on the server |
| `GET /api/health` | Process is up |
| `GET /api/ready` | Database reachable and a rule set is active; calls no third party |

## Providers

Each kind of provider is a `Protocol` in `planning/domain/` with one adapter per vendor under
`planning/adapters/<vendor>/`:

| Protocol | First adapter | Chosen by setting |
|---|---|---|
| `RouteProvider` | Mapbox | `ROUTE_PROVIDER` |
| `Geocoder` | Mapbox | `GEOCODER` |
| `WeatherProvider` | Open-Meteo | `WEATHER_PROVIDER` |

An adapter has a `client.py` (async HTTP, transport injected, timeouts and retries from settings)
and a `protocol.py` (pure request building and response parsing into domain objects, with unit
conversion to metric). Adding a vendor is one new folder and one entry in the wiring table.

## Failure behavior

| Situation | Result |
|---|---|
| Route provider down or times out | Catalog error; nothing to show |
| No route between the points | Catalog error naming both places |
| Fewer than 3 routes after topping up | Normal result with a notice |
| A top-up request fails | Skipped; the routes already found are returned |
| Some weather cells fail | Routes returned; affected checkpoints Unknown; a warning says how many |
| All weather fails | Routes returned with every level Unknown, no recommendation, and a clear error line |
| Heatmap grid fails | Routes and recommendation stay; the heatmap shows as unavailable |

## Bounds (settings or constants, never literals)

Maximum route distance, maximum checkpoints per route, maximum grid cells, corridor buffer,
forecast window, outbound concurrency, timeouts, retry count, cache lifetimes, request rate limit.

## Log events

`trip.requested`, `trip.rejected` (reason), `routes.fetched` (count, provider, round), `routes.rejected` (round, reason),
`weather.fetched` (cells requested, cache hits, misses, failures), `trip.planned` (route
count, recommended route, duration), `grid.built` (cells, cell size, hours).
