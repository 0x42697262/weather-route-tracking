# Product requirements

## Problem

Before a trip, a truck driver needs to know which route is safest given the forecast at the time
they will actually be on each stretch of road, and how heavy their load is. High wind is far more
dangerous for a heavy trailer, and a storm that clears before the truck arrives does not matter.

Drivers use this on a phone or tablet in the cab. The answer has to be readable at a glance.

## What the driver enters

- Origin
- Destination
- Departure date and time
- Load weight
- Checkpoint spacing (optional; defaults to 25 miles)
- Whether to add rest stops (optional, under Advanced options; on by default)

No account is needed. Nothing is stored per driver.

## What the app does

1. **Finds 3 alternative routes** between origin and destination. Routes, place search and
   forecasts come from external providers (`adr/0002`). When the provider's first
   answer has fewer than 3, the app asks again in other ways (avoiding tolls, avoiding highways,
   through a detour point) until it has 3 distinct routes. Only if no third distinct route exists
   does it show fewer, and it says so.
2. **Places checkpoints along each route** at the chosen spacing: 10, 25 or 50 miles.
3. **Looks up the forecast at each checkpoint for the time the truck gets there**: departure time
   plus the drive time to that point. Not the current weather.
4. **Rates the risk at each checkpoint**, and from that each stretch of road, using the risk model
   below.
5. **Recommends one route**, trading off weather risk against travel time using the ranking below.
6. **Shows everything on a map**: every route colored stretch by stretch by its risk level, its
   checkpoints with their risk level and arrival time, and a summary per route.
7. **Shows a heatmap around the routes** with a time slider covering 48 hours from departure. By
   default it shows the combined risk for the entered load; wind, rain and snow can be viewed one
   at a time. A marker on each route shows where the truck is at the selected hour.

## Risk model

Levels, lowest to highest: **Low, Moderate, High, Severe, No Travel**. These five are fixed.

A checkpoint's level is the worst level across its weather conditions, after the load adjustments.
"Wind" is sustained wind speed, not gusts.

### Weather thresholds (default rule set)

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind speed (mph) | under 25 | 25 to under 35 | 35 to under 45 | 45 to under 55 | 55 and above |
| Rain (in/hr) | under 0.10 | 0.10 to under 0.25 | 0.25 to under 0.50 | 0.50 to 1.00 | over 1.00 |
| Snow (in/hr) | under 0.5 | 0.5 to under 1.0 | 1.0 to under 2.0 | 2.0 to 3.0 | over 3.0 |

**Edge values:** a value exactly on a band edge belongs to the higher level, except the top edge of
rain and snow: exactly 1.00 in/hr of rain and exactly 3.0 in/hr of snow are Severe, and only values
above them are No Travel. Wind bands are continuous: 34.9 mph is Moderate, 35.0 mph is High.

### Load adjustments (wind only)

| Wind speed | Load | Level |
|---|---|---|
| 55 mph and above | any | No Travel |
| 45 to under 55 mph | over 30,000 lb | No Travel |
| 35 to under 45 mph | over 40,000 lb | Severe |

### From checkpoints to stretches

Each stretch of road between two neighboring checkpoints takes the **worse** level of its two ends.
A route's distance at each level is the sum of its stretches at that level.

### Ferries

Some routes include a ferry crossing, where the truck rides a roll-on/roll-off ferry (for example
between Philippine islands). Ferries are assumed to run as scheduled. A ferry stretch is not rated
by the weather thresholds, which are written for driving: the weather data has no wave
information, and whether a ferry sails in bad weather is the operator's decision. Instead it takes
a constant from the rule set, by default **not rated**: it is drawn and labeled "Ferry", its
distance is reported but left out of the ranking and the average, and the route shows a warning to
check with the ferry operator. Ferry time is the routing provider's estimate and counts as time not
driving.

### Arrival times

Arrival time at a checkpoint is the departure time, plus the truck's driving time to that point,
plus any rest taken before it.

- **Truck driving time** comes from the routing provider's truck routing, which takes the truck's
  weight (empty weight, default 32,500 lb, plus load) and top speed. It is then scaled by a factor (default 1.0) and
  capped at the truck top speed (default 65 mph).
- **Rest** follows a driving-and-rest clock: a 30-minute break after 8 hours of driving, and 10
  hours off after 11 hours of driving or 14 hours on shift. A driver can turn it off for a trip where the truck keeps moving, such as two
  drivers taking turns.
- Staff can change every one of these numbers.

## Route ranking

Compare routes on these, in order; a later one only breaks ties in the earlier ones:

1. Least distance at **No Travel**
2. Least distance at **Severe**
3. Least distance at **High**
4. Lowest **average risk**: levels scored Low = 0, Moderate = 1, High = 2, Severe = 3,
   No Travel = 4, averaged over the route weighted by distance
5. Shortest **travel time**

A route with any No Travel distance stays visible with a clear warning. If every route has No
Travel distance, the app recommends none and says so.

A stretch with no forecast is Unknown. Its distance is shown with a warning, stays out of the
ranking, and is left out of the average.

A route with too much Unknown distance is not recommended: by default a route of which more than
25% has no forecast cannot be the recommendation, and the next route in the ranking is recommended
instead. Its card says why. If no route qualifies, the app recommends none and says so. Staff set
the share in the rule set (`max_unknown_share`); setting it to empty removes the limit, so Unknown
distance then never stops a recommendation.

## Times

The driver enters the departure in their device's time zone. Every time on screen (arrival times,
the slider, rest stops) is shown in that same zone, labeled with it, e.g. "3:40 PM CST". The
server works in UTC.

## Units

The server works in metric (km, km/h, mm/h, cm/h, kg). What the driver sees is a display
preference: imperial (mi, mph, in, lb) by default, switchable to metric. Rule set thresholds keep
the unit staff entered them in.

## Configuration

The values in this document are the **default rule set**, not hard limits of the product.

- **Staff (owners, admins)** manage the business rules in an internal admin area. In the first
  version: weather thresholds for wind, rain and snow (in any supported unit, e.g. mph or km/h),
  load rules, truck speed (factor and top speed), rest rules and the allowed checkpoint spacings. Every change is a new,
  audited version; one version is active at a time and an earlier one can be restored.
- **Later, not in the first version:** new weather conditions from the provider's available fields,
  and an editable ranking order.
- **The five risk levels are fixed.** Staff move the cutoffs and add rules, not levels.
- **Drivers** choose the checkpoint spacing per trip (from the values staff allow), whether rest
  stops are added, and display
  preferences: units, map style, heatmap layer.
- **Whoever deploys** chooses the routing, geocoding and weather providers and the map tile source
  (OpenFreeMap by default).
  The first version ships one provider of each kind.
- Every result shows which rule set version produced it.

## Screen layout

A full-screen map with a bottom sheet that the driver drags between three heights:

1. **Peek:** one line with the verdict, e.g. "Take Route B · Low risk · 5 h 20 m".
2. **Half:** one card per route with its summary.
3. **Full:** the trip form, or one route's details.

The time slider sits just above the sheet. On a tablet held sideways the sheet becomes a side
panel. The first version has a light theme only.

## Quality bar

- Risk ratings and the recommendation are exact: every band edge and ranking rule is tested.
- The map, heatmap and time slider must feel smooth on a phone, including on long routes.
- The app is deployed and publicly reachable over HTTPS.

## Limitations of the first version

- Truck routing uses weight and top speed only. Vehicle height, length, axle weight and hazardous
  goods are not sent, so restrictions on those are not considered.
- Rest stops are placed where a limit is reached, not at real truck stops. Weekly hour limits are
  not modeled.
- Routes added by topping up (avoiding tolls or highways, or through a detour point) can be less
  natural than a provider's own alternatives.
- Routing and place search use TomTom. HERE, OpenRouteService and Mapbox are the alternatives, not
  built. Before commercial use, TomTom needs a subscription plan
  (`adr/0002-providers-behind-protocols.md`).
- Rest rules default to United States federal limits and apply to every trip, including trips in
  other countries; staff can change them, but there is one set for all countries.
- Border crossing wait times are not modeled.
- Ferry crossings are assumed to run. Their durations are the routing provider's estimates; ferry
  schedules, waiting time and cancellations are not modeled.
- On the free weather tier, about two trips a minute can be planned with no cached weather; more
  are slower or show some Unknown weather.
- A narrow band of bad weather between two calm checkpoints is not seen by the route summary; the
  heatmap still shows it.
- Weather beyond the forecast range is shown as unknown, never as Low.
- No accounts, saved trips or trip history.

## Open questions

None open.
