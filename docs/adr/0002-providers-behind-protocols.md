# 0002. Providers behind protocols; Mapbox and Open-Meteo first

Status: accepted, 2026-11-16

## Context

Routing, geocoding and weather come from third parties. The product may need to change or add
vendors (cost, terms, coverage, truck-specific routing). A test of the public OSRM demo server
returned 1 and 2 routes on two trips when asked for 3 (`facts.md` F-1), so it is not the default.

## Decision

Services depend on three protocols: `RouteProvider`, `Geocoder`, `WeatherProvider`. Each vendor is
one adapter folder. Whoever deploys picks the active adapter of each kind with a setting. The first
version ships one adapter per kind: Mapbox for routing and geocoding, Open-Meteo for weather.

## Consequences

- Adding a vendor is one folder and one wiring entry; domain and services do not change.
- Provider choice is an operator setting, not something drivers or staff change at run time.
- Mapbox has no truck profile (`facts.md` F-3); truck driving times are estimated from car times
  (`trip-planning.md`). A vendor with truck routing can be added later (F-11).
- No route result is stored on the server, because a provider's terms can forbid it (F-8).
- Open-Meteo's free tier is believed to be non-commercial (`facts.md` V-9); a commercial launch
  needs its paid tier or another adapter.
- Provider tokens stay on the server; the browser calls only this app's API.
- **Alternatives for routing, not built:** TomTom, HERE and OpenRouteService. All three document
  truck routing by vehicle weight and height (F-11), and can return more than 2 routes per request.
  Free quotas and known terms are in F-40 to F-42; the remaining gaps are V-17.
- **Before commercial use:** Mapbox's terms require an additional license for applications
  "primarily intended for use within vehicles" (F-10). The first version proceeds on Mapbox; that
  license must be settled, or the routing adapter changed, before the app is offered to drivers
  commercially.
