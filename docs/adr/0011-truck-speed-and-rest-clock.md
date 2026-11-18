# 0011. Truck speed and a driving-and-rest clock

Status: accepted, 2026-11-16

## Context

The weather a truck meets depends on when it reaches each point. The routing provider returns car
drive times and has no truck profile (`facts.md` F-3). Long trips also include breaks and off-duty
time, which move every later arrival.

## Decision

- Truck driving time is derived per route segment: car speed times a factor (default 1.0), capped
  at a truck top speed (default 65 mph).
- Rest is added by a driving-and-rest clock with the United States limits as defaults: a 30-minute
  break after 8 hours of driving, 10 hours off after 11 hours of driving or 14 hours on shift.
- Every number is a rule set field that staff can change. Rest is also a per-trip option the driver
  can turn off, for trips where the truck keeps moving.
- Both live in one pure function that returns elapsed time and the stops it inserted.

## Consequences

- Default arrival times are later than the provider's car times on fast roads and on long trips.
- Sources for the defaults are recorded (F-13, F-15, F-16 to F-19).
- Not modeled: state-specific truck limits, real stopping places, weekly hour limits, on-duty time
  that is not driving. The app estimates; it does not check legal driving hours.
- Smarter stop placement or waiting out a storm can replace the function without touching
  classification or ranking.
