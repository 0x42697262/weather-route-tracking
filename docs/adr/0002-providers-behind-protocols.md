# 0002. Providers behind protocols; TomTom and Open-Meteo first

Status: accepted, 2026-11-16. Revised the same day: TomTom replaced Mapbox as the first routing and
place search adapter.

## Context

Routing, place search and weather come from third parties. The product may need to change or add
vendors (cost, terms, coverage, truck routing). Mapbox was the first choice, then dropped:

- its Directions API has no truck profile and returns at most 2 routes per request (`facts.md`
  F-3, F-5);
- its terms forbid caching route results and require an extra license for in-vehicle apps (F-8,
  F-10).

TomTom routes trucks (`travelMode=truck`, vehicle weight, top speed), returns up to 5 alternatives
per request, and has a free tier of 20,000 routing requests a month without a card (F-40, F-43).

## Decision

Services depend on three protocols: `RouteProvider`, `Geocoder`, `WeatherProvider`. Each vendor is
one adapter folder. Whoever deploys picks the active adapter of each kind with a setting. The first
version ships one adapter per kind: TomTom for routing and place search (its Places Search API,
which TomTom recommends for new integrations, F-50), Open-Meteo for weather.

## Consequences

- Adding a vendor is one folder and one wiring entry; domain and services do not change.
- Provider choice is an operator setting, not something drivers or staff change at run time.
- Travel times are truck times from the provider; the app's speed factor and cap apply on top
  (`trip-planning.md`).
- Nothing from TomTom is cached or stored on the server: its terms forbid caching results "to
  serve multiple clients or users" (F-52), and Mapbox's forbid it too (F-8).
- Open-Meteo's free tier is non-commercial (F-31); a commercial launch needs its paid tier or
  another adapter.
- Provider keys stay on the server; the browser calls only this app's API.
- **Alternatives for routing, not built:** HERE and OpenRouteService (truck routing, F-11, F-41,
  F-42) and Mapbox (car routing only). Remaining gaps in their terms are V-17.
- **Before commercial use:** TomTom's terms limit the free license to evaluation and testing
  (F-52); a commercial launch needs a subscription plan.
