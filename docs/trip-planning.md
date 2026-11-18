# Trip planning

How a trip request becomes routes, checkpoints, arrival times, weather and a recommendation, and
how the heatmap grid is produced. Risk classification and ranking are in `risk-model.md`.

Items marked UNVERIFIED depend on provider behavior listed in `facts.md` and must be checked before
the code relies on them.

## Planning a trip (`POST /api/v1/trips`)

Input: origin and destination as coordinates plus the label the driver picked, departure time
(UTC), load weight, checkpoint spacing. Weight and spacing arrive as value plus unit and are
converted to metric at the API boundary.

Request body (`planning/api/trip_schemas.py`, unknown fields rejected):

    {"origin": {"label", "latitude", "longitude"},
     "destination": {"label", "latitude", "longitude"},
     "departure_utc": "2026-11-18T14:00:00Z",
     "load_weight": {"value": 40000, "unit": "lb"},
     "checkpoint_spacing": {"value": 25, "unit": "mi"} | omitted,
     "include_rest_stops": true | omitted}

- `departure_utc` must carry an offset; a naive time is rejected. Any offset is accepted and
  converted to UTC.
- `load_weight` takes `kg`, `lb` or `t`; `checkpoint_spacing` takes `km`, `mi` or `m`. A unit of the
  wrong dimension is a field error. The spacing must equal one of the rule set's spacings after
  conversion.
- Latitude is within ±90 and longitude within ±180; labels are 1 to 200 characters.

Order of work in the service (`planning/services/plan_trip.py`), cheap checks first:

1. **Schema validation** of the request.
2. **Local rules**, before any outbound call, in this order: the options pass the option registry
   (spacing allowed, load 0 to 50,000 kg and required, rest stops); the departure is at most 15
   minutes in the past and at most the weather provider's horizon minus the 48-hour window ahead
   (96 hours with Open-Meteo's 144); origin and destination are more than 1 km apart in a straight
   line; the straight line is not longer than `TRIP_MAX_DISTANCE_KM`; the checkpoints the straight
   line would need fit both `TRIP_MAX_CHECKPOINTS_PER_ROUTE` and `WEATHER_MAX_CELLS_PER_TRIP`.
   The straight line is a lower bound of the road distance, so these checks never reject a trip
   the road checks would accept.
3. **Routes:** ask the route provider for alternatives, then top up to 3 distinct routes (below).
   Zero routes is a catalog error. Fewer than 3 after topping up is a normal result, flagged in
   the response.
4. **Checkpoints and arrival times** per route (pure, below).
5. **Weather:** one deduplicated lookup for every checkpoint of every route (below).
6. **Classify, build stretches, summarize, rank, recommend** (pure, `risk-model.md`).
7. **Return the result.** The plan is not stored on the server.

After routing, the fastest route's road length and checkpoint count are checked again against the
same bounds (an `invalid_request` naming `destination` or `checkpoint_spacing`). An alternative
that breaks them is dropped instead. Before the weather lookup, the distinct cells of every
checkpoint are counted; more than `WEATHER_MAX_CELLS_PER_TRIP` rejects the trip with no weather
call.

The response (`TripOut`; every value metric, every time UTC):

| Field | Content |
|---|---|
| `rule_set_version`, `stretch_method` | The rule set used |
| `departure_utc`, `vehicle_weight_kg` | Departure, and empty weight plus load |
| `options_used` | `checkpoint_spacing_km`, `include_rest_stops`, `load_kg` |
| `routes` | In ranking order (below) |
| `ranking` | `key_names` and per route `keys[{route_id, values, has_known_weather}]` |
| `recommended_route_id`, `no_recommendation_reason` | Exactly one is set |
| `routes_requested`, `routes_found`, `fewer_routes_than_requested` | 3, the count kept, and the notice flag |
| `rounds_tried` | The rounds that sent a request, in order (`fastest`, `avoid_tolls`, ...) |
| `warnings` | Trip warnings: `gross_weight_over_limit` (over 80,000 lb), `fewer_routes_than_target`, `weather_partial`, `weather_unavailable` |
| `weather` | `cell_size_deg`, `cells_requested`, `cells_missing`, `unknown_checkpoints`, `refined_samples` |

Each route: `id` (`route-1`...), `rank` (1 is best), `recommended`, `source` (also the label's
text key), `distance_km`, `polyline` (the simplified line, Google encoded precision 5),
`refined_samples`, and:

- `summary`: `distance_km_by_level` (every level, 0 included), `unknown_km`, `ferry_km`,
  `total_km`, `average_risk` (null with no known weather), `blocked`, `driving_s`, `rest_s`,
  `ferry_s`, `travel_time_s`, `arrival_utc`, `warnings`.
- `checkpoints[]`: `index`, `distance_km`, `latitude`, `longitude`, `arrival_utc`, `values`
  (variable to value or null), `level` (null when Unknown or on a ferry), `weather_level` (the
  forecast's level, also on a ferry), `decided_by`, `conditions[{variable, value, band_level,
  level}]`, `on_ferry`.
- `stretches[]`: `start_km`, `end_km`, `level` (null for Unknown and an unrated ferry), `kind`,
  `polyline`. Neighbors with the same level and kind are merged for display; each polyline is cut
  from the simplified line at the stretch ends.
- `stops[]`: `kind` (break or off duty), `distance_km`, `latitude`, `longitude`, `start_utc`,
  `duration_s`.
- `positions_by_hour[]`: 49 entries, hours 0 to 48 after departure: `hour`, `distance_km`,
  `latitude`, `longitude`. The truck holds still during a stop and at the destination after
  arrival. The slider uses these, so the client computes no position.

Distances are rounded to 3 decimals, coordinates to 6, durations to whole seconds. A 330 km
three-route trip measured 43 KB (4 KB compressed).

### Reaching 3 routes

The target is 3 distinct routes. The first request asks TomTom for several alternatives
(`ROUTE_ALTERNATIVES_REQUESTED`, up to 5) with `alternativeType=anyRoute`, so it usually holds 3
distinct routes on its own. TomTom notes that "fewer alternative routes may be returned if either
fewer alternatives exist" (`facts.md` F-40), and the public OSRM server returned 1 and 2 routes on
two test trips (F-1), so the top-up rounds below remain for those cases.

The service (`planning/services/route_options.py`) asks in rounds and stops as soon as it holds 3:

| Round | Request | Label on the route card |
|---|---|---|
| 1 | Fastest route with the provider's own alternatives | "Fastest", "Alternative" |
| 2 | Avoid toll roads | "Avoids tolls" |
| 3 | Avoid highways | "Avoids highways" |
| 4 | Through a detour point: a point pushed sideways from the middle of the fastest route, one side and then the other | "Detour" |

- Each adapter declares which rounds it supports; unsupported rounds are skipped. TomTom supports
  `avoid=tollRoads` and `avoid=motorways` (F-43). TomTom warns that avoiding motorways on routes of
  about 500 km or more "may result in computation timeouts", so round 3 is skipped for routes that
  long.
- **Distinct (pure, `planning/domain/route_distinct.py`):** a new route is kept only if the share
  of its length that runs along an already kept route is under a limit, and its drive time is
  within a limit of the fastest route's. Both limits are constants, starting at an overlap under
  70% and a travel time at most 1.5 times the fastest. On 5 live trips this kept 3 routes from the
  first request on 4 of them (`facts.md` F-46). This drops repeats and detours no driver would
  take.
- The first request asks for `ROUTE_ALTERNATIVES_REQUESTED` alternatives, lowered to the
  provider's maximum. Its first route is "Fastest", the others "Alternative". Top-up requests ask
  for no alternatives.
- The detour round sends one request per side, so it can cost two extra requests. A fastest line
  with no length has no detour point and the round is skipped.
- A cap on extra requests per trip (`ROUTE_MAX_EXTRA_REQUESTS`) bounds the cost.
- Requests are sent one after another, never in parallel. Only the first request's errors reach
  the driver; a failing top-up request is logged (`routes.rejected`, reason `request_failed`) and
  the search goes on. Every skipped round is logged (`routes.round_skipped`: `unsupported`,
  `fastest_too_long`, `no_via_point`, `request_cap`).
- Each kept route records how it was found. The fastest route is always first.
- **Fallback when the rounds run out.** Routes rejected only for not being distinct (overlap or
  time) are set aside. If the rounds leave fewer than 3, the set-aside routes fill the remaining
  places, most different first (lowest overlap with the kept routes, measured again), then
  fastest. A set-aside route is never used when it nearly repeats a kept route (overlap 97% or
  more) or takes more than 3 times as long as the fastest (`FALLBACK_MAX_OVERLAP_SHARE`,
  `FALLBACK_MAX_TIME_RATIO`). It is labeled by why it was set aside: `similar` (overlap) or
  `slower` (time), and logged as `routes.fallback_kept`. Ranking then treats it like any route.
  Why: the product promises 3 options; a labeled similar or slower route is more useful to a
  driver than a missing one, and the ranking still puts a much slower route last.
- If even the fallback leaves fewer than 3, the response says how many were found.

### Ferries

Routes outside well-mapped areas can include ferry sections (`facts.md` F-54: Manila to Cebu has
two). They are requested with `sectionType=ferry`, kept on the route and labeled on the map.
Ferries are assumed to run. A ferry stretch takes the rule set's constant `ferry_level`, by
default not rated (`risk-model.md`). Its time is the provider's estimate, with no schedule or
waiting time, and the rest clock counts it as time not driving.

### Route geometry

TomTom returns 3,000 to 20,000 points per route (F-47). The full line is used on the server for
checkpoints and arrival times. The line sent to the browser is simplified (Douglas-Peucker, with a
tolerance constant, 30 m, not yet checked against live routes) so the response stays small and the map draws fast; stretches are
cut from the simplified line at the checkpoint positions.

Times in the provider's response carry local offsets and can change zone along the route. The
adapter does not read those clock times: it uses the relative `travelTimeInSeconds` in `progress`
and the summary, and the server adds them to the UTC departure it sent. Zone changes therefore
cannot shift an arrival.

### Checkpoints (pure)

- Walk the route's line, adding up great-circle distance between points.
- Put a checkpoint at distance 0 (origin), then at every multiple of the spacing, then at the
  destination. If the last multiple falls closer to the destination than 25% of the spacing, it is
  dropped so the final stretch is not a sliver. A share follows whichever spacing the driver picks;
  a fixed km gap would not.
- A checkpoint's position is interpolated on the line segment it falls in.
- A hard cap on checkpoints per route (setting) rejects requests that would exceed it, with an
  error that suggests a wider spacing.

### Truck speed and arrival times (pure)

The route request carries the truck: `travelMode=truck`, the vehicle's weight (empty weight plus
load, so roads with weight limits are avoided), `vehicleCommercial=true`, and the truck top speed
as `vehicleMaxSpeed` (`facts.md` F-43). TomTom then returns **truck** travel times. With
`extendedRouteRepresentation=travelTime` and `distance`, the response has a `progress` list of
cumulative time and distance at route points; times between listed points are interpolated by
distance, which TomTom's documentation describes as the intended use (F-44).

The app adjusts those times only by settings staff control:

    truck_speed = min(provider_speed × truck_speed_factor, truck_max_speed)
    truck_time  = segment_distance ÷ truck_speed

- `provider_speed` comes from the provider's per-segment distance and time. If a provider gives
  only a total, the route is treated as one segment at its average speed.
- **`truck_speed_factor`** scales every segment. Default 1.0, which leaves the provider's truck
  times unchanged.
- **`truck_max_speed`** default 65 mph. Fleets set limiters "most often at speeds from 60 to 70 mph"
  (F-13). It is sent to a provider that accepts a vehicle top speed, and applied again here so the
  result is the same with a provider that does not. It may be empty, meaning no cap.
- **`empty_vehicle_weight`** default 32,500 lb: an empty sleeper tractor (19,000 lb) and an empty
  53-foot dry van (13,500 lb) in EPA's heavy-truck rule (`facts.md` F-53). Vehicle weight sent to
  the provider = empty weight + load. A total over the federal 80,000 lb limit gets a warning; the
  trip is still planned.
- All of these live in the rule set, so staff change them in admin and the server supplies the
  defaults.
- With a car-only provider (an alternative adapter), the same formula turns car times into truck
  estimates; the factor and the cap then matter more (F-12, F-15).

`arrival = departure + truck driving time to the checkpoint + rest time taken before it`.

The departure is sent to the provider as `departAt` with an explicit UTC offset, because without
one TomTom assumes the origin's time zone (F-44).

All times are timezone-aware UTC. `now` is passed into the service by the view; domain code never
reads the clock. The client converts the departure from the device's time zone to UTC before
sending, and converts every returned time back for display (`frontend.md`).

### Rest stops (pure)

Long trips cannot be driven without stopping, and every stop shifts the weather the truck meets
later. Arrival times therefore come from one function, `build_timeline`, that returns elapsed time
and the stops it inserted. The option defaults to the rule set's
`rest_rules.enabled`.

**Method: a driving-and-rest clock.** Walk the route's segments in order, keeping three counters:
driving time since the last break, driving time in this shift, and time since the shift began.

| When this limit is reached | Insert | Then reset | Default from |
|---|---|---|---|
| 8 hours of driving since the last break | A 30-minute break | Driving since last break | F-19 |
| 11 hours of driving in the shift, or 14 hours since the shift began | 10 hours off duty | All three counters | F-16, F-17, F-18 |

- A segment that crosses a limit is split at the point where the limit is reached, and the stop is
  placed there.
- Breaks count toward the 14-hour window. Off-duty time starts a new shift.
- Ferry time counts toward the 14-hour window but does not reset the break counter. If the window
  runs out on a ferry, off duty starts when the ferry docks.
- A provider segment with no distance but some time keeps its time and counts as driving. A
  segment with distance but no time takes distance ÷ truck top speed, or 0 s with no top speed.
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
  (F-31) and 600 a minute (F-48). The maximum cells per trip (checkpoints plus heatmap) is a
  setting sized from that quota, and a provider call counter is logged per trip.
- The adapter reads Open-Meteo's `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers. When the
  next batch would exceed the remaining calls, it waits for the reset if that is within the
  request's time budget, and otherwise returns the cells it has; the rest are Unknown.
- A checkpoint whose hour is outside the forecast range, or whose cell failed to load after
  retries, has no weather and its level is Unknown.
- **Refine** (`stretch_method` `refine`, `risk-model.md`): after the checkpoints, up to
  `REFINE_MAX_DEPTH` (4) rounds sample the midpoint of every gap whose ends differ in level
  (Unknown counts as a level) and is longer than one weather cell (`cell_size_deg` in km, about
  11 km at 0.1°).
  Each round makes one more weather call for its new cells only. Refinement uses what is left of
  `WEATHER_MAX_CELLS_PER_TRIP` after the checkpoints; samples in cells beyond it are skipped, never
  an error. `refine.sampled` logs the depth and sample count.

### No stored plans

The server keeps no copy of a plan. A routing provider's terms can forbid caching or storing route
results (Mapbox does, `facts.md` F-8; TomTom's terms are unverified, V-17), and a design that
never stores them works under any
provider's terms. Forecast cells are cached; they come from the weather provider, whose terms are
checked separately (V-9).

## Heatmap grid (`POST /api/v1/weather-grid`)

Separate from planning so routes and the recommendation appear first.

1. Read the request: the route lines the client already holds (encoded), the departure time and
   the load. The lines are untrusted input: their count, point count and total length are checked
   against the same caps as a plan.
2. **Corridor (pure):** grid cells within a buffer distance (25 km) of any route. A cell is in when
   a route passes within the buffer plus half the cell's diagonal of its center, so growing cells
   leave no holes along the route. Cell size starts at the provider's resolution and doubles until
   the cell count is under `WEATHER_MAX_CELLS_PER_TRIP`, so long trips stay bounded. Cell centers
   equal the checkpoint lookup's cell keys.
3. **Forecast** for every cell for each hour from departure to departure plus 48 hours, through the
   same cache as above.
4. **Classify (pure)** every cell and hour with the driver's load, using the same function as
   checkpoints.
5. Return, per cell: its center, and arrays with one entry per hour: the value and the level for
   wind, rain and snow (metric), and the combined level. Hours with no forecast are `null`. The
   client colors every layer from the levels, so it holds no thresholds.

Request (`WeatherGridIn`): `{"lines": [route polyline, ...], "departure_utc", "load_weight":
{value, unit}}`. The lines are the routes' `polyline` values. Checked in this order, all before
any outbound call: 1 to 3 lines of at most 200,000 characters each (schema); the load against the
option registry; the departure range as for a trip; each line decodes, has 2 to 20,000 points and
is not longer than `TRIP_MAX_DISTANCE_KM` (the error names `lines.<index>`); the corridor fits
`WEATHER_MAX_CELLS_PER_TRIP` after growing.

Response (`WeatherGridOut`), parallel arrays to keep it small:

| Field | Content |
|---|---|
| `rule_set_version`, `departure_utc`, `cell_size_deg`, `cells_missing` | As named; `cell_size_deg` is the grown size |
| `hours_utc` | 49 hours, departure to departure plus 48 |
| `levels` | The level keys by score (`low` ... `no_travel`); level entries below are indexes into it |
| `latitudes`, `longitudes` | Cell centers, one per cell |
| `layers[]` | `key`, `variable` (null for the combined `risk` layer), `text_key`, `levels[cell][hour]` (index or null), `values[cell][hour]` (metric, 1 decimal, or null; null for `risk`) |

Measured on the compose stack (3 routes Dallas to Oklahoma City: 193 cells at 0.2°, 269 KB; 2
routes Seattle to Portland: 292 cells at 0.1°, 398 KB, 22 KB with gzip). Caddy compresses the
response, so its size on the wire is about 6% of the raw size.

The whole 48 hours go out in one response. Moving the slider never calls the server.

## Other endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/options` | What the driver may choose and the defaults, from the active rule set: `rule_set_version`, `forecast_window_hours`, `stretch_method`, `routes_target`, `departure_window {past_tolerance_minutes, max_hours_ahead}`, `options`, `risk_levels`, `weather_variables`, `heatmap_layers`, `attribution[{text, url}]` |
| `GET /api/v1/places?query=&session=` | Place suggestions (TomTom Places Suggest, cities and areas): `{suggestions: [{id, title, subtitle}]}`. The trimmed query needs at least 3 characters (at most 100); `session` must be a UUID, as TomTom's `Session-Id` asks; the client debounces typing. A bad query calls nothing |
| `GET /api/v1/places/{id}` | The picked place: `{id, label, latitude, longitude}` (TomTom Places Details). Called once per pick; an unknown id is `place_not_found` (404) |

`attribution` lists the notices of the configured providers, without repeats: `©TomTom` (routes),
`©TomTom, ©OpenStreetMap` (place search) and `Weather data by Open-Meteo.com` with a link to
`https://open-meteo.com/`. The client shows them on the map; the fake providers have their own.

**Rate limits** (`core/middleware.py`): counted per client address in fixed one-minute windows in
the cache. Trips and the weather grid each allow `RATE_LIMIT_TRIPS_PER_MINUTE`, counted
separately; the two places endpoints share a constant 60. Over the limit the answer is 429 with
the `rate_limited` catalog error. The address is the last `X-Forwarded-For` entry (the one Caddy
added) only when `BEHIND_PROXY`; otherwise the socket peer.

Every response carries `X-Request-ID`: a valid incoming one is kept, otherwise a new one is made.
Every log line of the request carries it as `request_id`.
| `GET /api/health` | Process is up |
| `GET /api/ready` | Database reachable and a rule set is active; calls no third party |

## Providers

Each kind of provider is a `Protocol` in `planning/domain/` with one adapter per vendor under
`planning/adapters/<vendor>/`:

| Protocol | First adapter | Chosen by setting |
|---|---|---|
| `RouteProvider` | TomTom | `ROUTE_PROVIDER` |
| `Geocoder` | TomTom | `GEOCODER` |
| `WeatherProvider` | Open-Meteo | `WEATHER_PROVIDER` |

An adapter has a `client.py` (async HTTP, transport injected, timeouts and retries from settings)
and a `protocol.py` (pure request building and response parsing into domain objects, with unit
conversion to metric). Adding a vendor is one new folder and one entry in the wiring table.

## Failure behavior

| Situation | Result |
|---|---|
| Route provider down or times out | Catalog error; nothing to show |
| No route between the points (TomTom `NO_ROUTE_FOUND`, e.g. an island with no road link, or `MAP_MATCHING_FAILURE`, a point not near any road) | `no_road_route` (422): "There is no road route between these two places." |
| Provider returns 429 (over 5 requests a second) | Retried with backoff; then the catalog error for a busy provider |
| Fewer than 3 routes after topping up | Normal result with a notice |
| A top-up request fails | Skipped; the routes already found are returned |
| Some weather cells fail | Routes returned; affected checkpoints Unknown; a warning says how many |
| All weather fails | Routes returned with every level Unknown, no recommendation, and a clear error line |
| Heatmap grid fails | Routes and recommendation stay; the heatmap shows as unavailable |

## Bounds (settings or constants, never literals)

Maximum route distance, maximum checkpoints per route, maximum grid cells, corridor buffer,
forecast window, outbound concurrency, timeouts, retry count, cache lifetimes, request rate limit.

## Log events

Services (`planning/events.py`):

- `trip.requested` (departure_utc, rule_set_version), `trip.rejected` (reason: a `Rejection`
  value or the error code), `trip.planned` (route_count, recommended_route, duration_ms).
- `routes.fetched` (count, provider, round), `routes.rejected` (round, reason, overlap_share,
  time_ratio or error), `routes.round_skipped` (round, reason).
- `checkpoint.classified` (DEBUG: route_id, checkpoint, values, load_kg, level, decided_by),
  `refine.sampled` (depth, samples), `route.summarized` (route_id, source, total_km, unknown_km,
  average_risk, travel_time_s, warnings), `routes.ranked` (keys), `recommendation.none` (reason).
- `grid.requested` (lines), `grid.rejected` (reason), `grid.built` (cells, cell_size_deg, hours,
  cells_missing).
- `request.rate_limited` (scope, count), from the middleware.

Adapters (`planning/adapters/events.py`):

- `upstream.retry` (provider, operation, attempt, reason, delay_s) and `upstream.failed`
  (provider, operation, attempts, reason).
- `weather.fetched` (cells_requested, cache_hits, cache_misses, failures), from the forecast
  cache.
- `weather.batch_failed` (cells, error), `weather.rate_limit_wait` (wait_s),
  `weather.rate_limit_skipped` (cells, remaining_calls, wait_s).

The `httpx` logger is set to WARNING in `core/settings.py`, because at INFO it logs request URLs
and TomTom routing takes the key in the URL.
