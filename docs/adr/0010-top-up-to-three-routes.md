# 0010. Top up to 3 routes

Status: accepted, 2026-11-16. Replaces the earlier decision in this record to show only what the
provider's first answer contains.

## Context

The product promises 3 alternative routes. TomTom can return up to 5 alternatives per request,
but "fewer alternative routes may be returned if either fewer alternatives exist" (`facts.md`
F-40). Other providers return fewer per request: Mapbox at most 2 (F-5), and the public OSRM server
returned 1 and 2 on two test trips (F-1).

## Decision

The target is 3 distinct routes. After the provider's own alternatives, the app asks again in
rounds until it holds 3: avoiding tolls, avoiding highways, then through a detour point beside the
fastest route. A route is kept only if it is distinct from those already kept and not much slower
than the fastest. If the rounds run out, the app shows fewer and says so.

## Consequences

- The first request asks for more alternatives than needed, so most trips need no extra request.
  Extra requests are capped (`ROUTE_MAX_EXTRA_REQUESTS`).
- Avoiding motorways is skipped on routes of about 500 km or more, where TomTom warns of timeouts
  (F-43).
- Each route carries a label for how it was found, shown on its card.
- Detour routes can be less natural than a provider's own alternatives; the distinctness and
  slowness limits keep the worst out, and they are tried last.
- The rounds and the distinctness check are provider-independent; an adapter only declares which
  rounds it supports.
