# Extensibility

What is fixed in the first version, what it takes to change each thing later, and what the code
does now so that the change stays small. The rule behind all of it is in
`engineering-guidelines.md` section 7.3: never branch on one specific member of a set; give the set
a table and iterate.

## The sets, and where each table lives

| Set | Table | Each row carries |
|---|---|---|
| Risk levels | `shared/risk_levels.py` | key, score (order), `ranked` (has its own ranking key), `blocks_recommendation`, text key, color token name |
| Weather conditions | `shared/weather_variables.py` | key, metric unit, units staff may enter, text key |
| Units | `shared/units.py` | key, quantity, exact factor to the metric unit |
| Ranking keys | `planning/domain/ranking.py` | key, function from a route summary to a number |
| Stretch methods | `planning/domain/stretches.py` | key, function from samples to stretches |
| Providers | `core/wiring.py` | key, adapter factory |
| Heatmap layers | `planning/domain/options.py` | key, which value and level arrays it reads, text key |
| Error codes, log events, text | the catalogs per app | code or name, message |

Code reads properties from the row. Nothing compares against a particular key.

## Risk levels

Fixed at five in the first version: staff cannot add one, because a new level needs a color, a
label and a decision about ranking, which are not rule set data yet.

Adding a sixth level in code is one row plus its visuals:

1. Add the row with its score and flags.
2. Add a color token and a label on the frontend.
3. Add test cases.

That stays true because of how the rest is written:

- Summaries hold `distance_km_by_level`, a map keyed by level, not one field per level.
- The ranking key is built from the table: one distance per level flagged `ranked`, from the
  highest score down, then the average risk, then travel time. Today the flagged levels are
  No Travel, Severe and High.
- "No recommendation" is driven by `blocks_recommendation`, today set only on No Travel.
- The average risk uses each row's score.
- The validator checks band levels against the table.
- The frontend gets the level list from `GET /api/v1/options` and draws the legend, cards and
  colors by iterating over it.

Letting **staff** define levels later means moving that table into the rule set: a new
`schema_version`, old versions migrated on read, and color and label fields in the document. The
domain code does not change, because it already reads the table as data.

## Other changes and what they touch

| Change | What it takes | What is done now to keep it small |
|---|---|---|
| New weather condition (gusts, visibility, ice, temperature) | One row in the conditions table; the field mapping in each weather adapter; bands in a rule set | Classification iterates over the rule set's conditions. The weather adapter requests the variables the active rule set uses. Heatmap layers come from the server |
| Editable ranking order | Move the list of ranking keys from a constant into the rule set | The key is already built from a list of named functions |
| Another routing, geocoding or weather provider | One adapter folder; one wiring row | Services depend on protocols; all vendor specifics are in the adapter |
| More truck restrictions (height, length, axle weight, hazardous goods) | New fields on the trip or the rule set, passed by the adapter | The route request object already carries the vehicle; TomTom accepts these parameters (`facts.md` F-11, F-43) |
| A car-only routing provider | One adapter folder | The speed factor and cap already turn any provider's times into truck estimates |
| Different driving and rest rules (another country) | New numbers in the rule set | Speed and rest limits are fields, not constants (`trip-planning.md`) |
| Smarter stops (real truck stops, waiting out a storm) | A new arrival-time function behind the same interface | Arrival times come from one pure function that returns elapsed time and stops |
| A different way to turn samples into stretches | One function and one table row | Stretch method is chosen by key |
| A form instead of JSON for rule sets | A form generated from the schema, calling the same validator | One validator, one schema, both independent of the admin screen |
| Driver accounts and saved trips | An `accounts` app; a stored trip holds the driver's inputs and a rule set version, and is planned again when opened, because provider terms can forbid storing route results (`facts.md` F-8) | No per-user state anywhere; a plan is self-contained and names its rule set version |
| More than one server | Managed database and cache; a load balancer | No in-process state; cache and database are separate services; activation needs no cache flush |
| Dark theme | A second token set and a dark map style | All colors, including map layers, go through tokens |
| Another language | A second text catalog | No user-facing string outside the catalogs |
| More than 48 hours, more than 3 routes | Change a constant; later move it into the rule set | Both are named constants with bounds, not literals |

## What does not extend cheaply

- **The map library.** Replacing MapLibre means rewriting the map components.
- **The meaning of a checkpoint.** If risk were sampled continuously instead of at checkpoints,
  summaries, the checkpoint list and the tests would all change.
- **Metric on the server.** Every name and stored forecast assumes it.
