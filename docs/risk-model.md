# Risk model

How weather at a checkpoint becomes a risk level, how levels become distances per route, and how
routes are ranked. The product-level statement is in `SPEC.md`; this file is the exact behavior the
domain code and its tests follow.

All of this is pure domain code (`planning/domain/`): no I/O, no clock, no Django.

## Levels

The levels are one table (`shared/risk_levels.py`). Code reads a level's properties from its row
and never compares against a particular level, so a level can be added with one row
(`extensibility.md`).

| Level | Score | Has its own ranking key | Blocks a recommendation |
|---|---|---|---|
| Low | 0 | no | no |
| Moderate | 1 | no | no |
| High | 2 | yes | no |
| Severe | 3 | yes | no |
| No Travel | 4 | yes | yes |

"Worse" always means the higher score. A rule set cannot change this table in the first version.

A checkpoint with no forecast has **no level** (`None`), shown as "Unknown". Unknown is not a sixth
level and is never treated as Low.

## Step 1: classify each condition

A rule set gives each condition a list of bands. A band is a lower bound, whether that bound is
inclusive, and a level. A value below the first band is Low. The value takes the level of the
highest band whose lower bound it reaches.

Default rule set, as entered (imperial) and as evaluated (metric):

| Condition | Moderate from | High from | Severe from | No Travel from |
|---|---|---|---|---|
| Wind speed | ≥ 25 mph (40.2336 km/h) | ≥ 35 mph (56.32704 km/h) | ≥ 45 mph (72.42048 km/h) | ≥ 55 mph (88.51392 km/h) |
| Rain | ≥ 0.10 in/h (2.54 mm/h) | ≥ 0.25 in/h (6.35 mm/h) | ≥ 0.50 in/h (12.7 mm/h) | > 1.00 in/h (25.4 mm/h) |
| Snow | ≥ 0.5 in/h (1.27 cm/h) | ≥ 1.0 in/h (2.54 cm/h) | ≥ 2.0 in/h (5.08 cm/h) | > 3.0 in/h (7.62 cm/h) |

The only exclusive bounds are the No Travel bounds of rain and snow, because the source table
writes them as "over". Every other edge value belongs to the higher level.

Conversion factors are exact: 1 mi = 1.609344 km, 1 in = 25.4 mm, 1 lb = 0.45359237 kg.

Every converted threshold and every provider value is rounded to 9 decimals
(`shared/units.py` `round_measure`). Without it, 3.0 in/h became 7.619999999999999 cm/h and a
forecast of exactly 7.62 cm/h counted as "over" (No Travel instead of Severe); rain + showers
summed to 25.400000000000002 mm/h the same way. A test feeds raw provider values on every edge
through the adapter parser and the classifier.

## Step 2: apply load rules

A load rule says: when a condition's value is inside a range (lower bound inclusive, upper bound
exclusive) **and** the load is strictly over a weight, the level is at least the rule's level.

| Wind speed | Load over | Level at least |
|---|---|---|
| 45 to under 55 mph | 30,000 lb (13,607.7711 kg) | No Travel |
| 35 to under 45 mph | 40,000 lb (18,143.6948 kg) | Severe |

"55 mph and above is No Travel for any load" needs no load rule: the wind band already says so.

A load rule can only raise a level, never lower it.

## Step 3: the checkpoint's level

The worst of: each condition's band level, and every load rule that matched. The result records
which condition or rule decided it, so the UI and the log can say why
(`decided_by: "load_rule:wind_speed"`).

Worked examples with the default rule set:

| Wind | Rain | Snow | Load | Level | Decided by |
|---|---|---|---|---|---|
| 20 mph | 0 | 0 | 45,000 lb | Low | none |
| 38 mph | 0 | 0 | 40,000 lb | High | wind band (load is not over 40,000) |
| 38 mph | 0 | 0 | 40,001 lb | Severe | load rule |
| 50 mph | 0 | 0 | 30,001 lb | No Travel | load rule |
| 10 mph | 1.00 in/h | 0 | any | Severe | rain band (exactly 1.00 is not over) |
| 10 mph | 0.30 in/h | 2.5 in/h | any | Severe | snow band |

## Step 4: stretches

Checkpoints split a route into stretches. How a stretch gets its level is a method chosen by key in
the rule set (`stretch_method`). Per route, the summary holds the distance in km at each level
(`distance_km_by_level`), plus the Unknown distance.

### Method `worse_end` (built first)

Each stretch between two neighboring checkpoints takes the worse level of its two ends. If either
end is Unknown, the stretch is Unknown.

- Cautious: it never reports a stretch as safer than either of its ends.
- It overstates. When the level changes between two checkpoints, the whole stretch counts at the
  worse level, so the risky distance can be too long by up to one spacing per change.

### Method `refine` (the seed rule set still uses `worse_end`)

Start from the same checkpoints. Wherever two neighbors have **different** levels, take one more
sample at the midpoint (its own arrival time and forecast, classified the same way) and repeat on
each half that still has different ends, until a stretch is shorter than a minimum length or a
depth limit is reached. The remaining short mixed stretches take the worse end.

- The level change is located to within the minimum length instead of a whole spacing.
- Extra samples are spent only where the level changes. A change inside a 50-mile stretch with an
  8-mile minimum costs at most 3 samples.
- The minimum length defaults to the weather grid's cell size: finer samples would read the same
  forecast cell and add nothing.
- Samples added by refinement are not shown as checkpoints. The driver still sees checkpoints at
  the spacing they chose.
- Unknown counts as its own value, so the edge of missing weather is located the same way as a
  change of level.
- The depth limit is `REFINE_MAX_DEPTH` (4). Refinement spends only the weather cells the trip
  has left under `WEATHER_MAX_CELLS_PER_TRIP` (`trip-planning.md`, Weather lookup).
- The route's `refined_samples` and the trip's `weather.refined_samples` say how many samples
  were added.

### Designs considered

| Design | What it does | Why not the default |
|---|---|---|
| Worse of two ends | Above | Overstates by up to a spacing per change. Kept as the simple baseline |
| Nearest checkpoint | Each checkpoint owns half the stretch on each side | Unbiased on average, but understates as often as it overstates; half of a stretch next to a Severe checkpoint is reported at the calmer level |
| Refine by halving | Above | Chosen: keeps the cautious rule and removes most of its error |
| Sample every weather cell the route crosses | Risk at the full resolution of the forecast; checkpoints become display only | Most accurate, and the only design that sees a narrow storm between two calm checkpoints. Not chosen because the checkpoint spacing would no longer affect the result, which changes what the product promises. A candidate for later |

### A limit all checkpoint designs share

If two neighboring checkpoints are both calm, nothing between them is sampled, so a narrow band of
bad weather between them is missed. A smaller spacing reduces this. The heatmap shows such a band
even when the route summary does not.

## Step 5: ranking

Routes are sorted by this key, smallest first:

    (no_travel_km, severe_km, high_km, average_risk, travel_time_s)

The distance entries are generated from the level table: one per level that has its own ranking
key, from the highest score down. Travel time is the full elapsed time, rest included.

- `average_risk` = sum of (stretch score × stretch km) ÷ sum of stretch km, over stretches with a
  known level.
- Values are rounded before comparing (constants in `planning/domain/risk_constants.py`):
  distances to 2 decimals, average risk to 3, travel time to whole seconds, so floating-point
  noise never decides a ranking.
- Routes that tie on every entry keep their order from the route search (the fastest first).
- A route with no known weather sorts after every route that has some, and is never
  recommended. "Known weather" means distance rated from a forecast; a ferry rated by the
  constant `ferry_level` does not count, so a route that is all Unknown plus a rated ferry is not
  recommended.

**Recommendation:** the first route in that order, unless every route has distance at a level that
blocks a recommendation (No Travel); then there is no recommendation and the response says why.
The top-ranked route is then returned as `best_available_route_id` (and `best_available: true` on
the route), and the verdict reads "No safe route · best available is Route A · …". Why: the driver
still has to choose; naming the least bad route with its warning is clearer than naming none,
while `recommended_route_id` stays empty so no client mistakes it for a safe recommendation.
The reason is `every_route_blocked` when every route that has known weather is blocked, and
`no_known_weather` when no route has any.

A route with No Travel distance is still returned and drawn, with a warning.

## Heatmap cells

The combined-risk heatmap uses steps 1 to 3 on each grid cell and hour, with the load the driver
entered. The same function classifies checkpoints and cells; there is one implementation.

## Ferry stretches

A stretch on a ferry section of the route (the provider marks it) is not classified from weather.
Its level is the rule set's constant `ferry_level`, default `null`, meaning **not rated**. A
not-rated ferry stretch:

- is counted as `ferry_km` in the route summary, separately from every level and from Unknown;
- is left out of the ranking key and out of the average risk, like Unknown;
- adds a warning to the route ("Includes a ferry crossing; check with the operator").

Staff may set `ferry_level` to one of the five levels; ferry stretches then count at that level
like any other stretch. Checkpoints that fall on a ferry section still show the forecast, for
information only: their `level` is null and `weather_level` holds the forecast's level.

- A route with any ferry stretch carries the `ferry_crossing` warning, also when staff set a
  `ferry_level`.
- A checkpoint on a ferry keeps its weather level for the land stretches on either side of the
  ferry; only the ferry interval itself takes `ferry_level`.

## Unknown weather

Unknown distance is reported per route and warned about. It does not enter the ranking key and is
left out of the average risk.

It can stop a recommendation. The rule set's `max_unknown_share` (default 0.25; `null` means no
limit) is the largest share of a route's length with no forecast that a recommended route may
have; the share is rounded to 4 decimals and exactly the limit is allowed. A route over it keeps
its place in the ranking order but is skipped for the recommendation, with
`not_recommendable_reason: too_much_unknown_weather` on the route.

Why: Unknown is left out of the ranking key so that missing data never counts as safe or as
dangerous. But without a limit, a route that is 99% Unknown and 1% Low ranked above a fully
forecast route with some High distance and was recommended, which tells a driver the opposite of
what is known. The limit keeps the ranking order honest and only stops recommending a route the
app knows little about. Staff who prefer the plain ranking set the limit to `null`.

The exclusions are checked per route in this order: `no_known_weather`, `blocked` (distance at a
level that blocks a recommendation), `too_much_unknown_weather`; the first that applies is the
route's reason. When no route is recommended, the trip's reason is the latest of these that
stopped a route, so the driver hears the most specific cause: `no_known_weather` when no route
has a forecast, `too_much_unknown_weather` when some unblocked route was stopped only by the
limit, otherwise `every_route_blocked`.

Which forecast hour is read: an instant value (wind) reads the nearest hour, and at exactly half
past it reads the later one. A value summed over the preceding hour (rain, snow) reads the first
hour at or after the arrival. An arrival before the first forecast hour or after the last one has
no value, so that condition is Unknown.

## Wind

The wind condition is sustained wind speed. Gusts would be a separate condition
(`extensibility.md`).

## Log events

`checkpoint.classified` (DEBUG: values, load_kg, level, decided_by), `refine.sampled` (depth,
samples), `route.summarized`, `routes.ranked` (the key of every route), `recommendation.none`
(reason). Names live in `planning/events.py`; fields are listed in `trip-planning.md`.
