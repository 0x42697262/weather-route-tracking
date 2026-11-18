# 0010. Top up to 3 routes

Status: accepted, 2026-11-16. Replaces the earlier decision in this record to show only what the
provider's first answer contains.

## Context

The product promises 3 alternative routes. One Mapbox request returns at most 2: its API page is
inconsistent, but its Swift and Java SDKs both state a maximum of 2 (`facts.md` F-5). The public
OSRM server returned 1 and 2 routes on two test trips (F-1). TomTom and HERE can return more than
2 alternatives in one request (F-40, F-41).

## Decision

The target is 3 distinct routes. After the provider's own alternatives, the app asks again in
rounds until it holds 3: avoiding tolls, avoiding highways, then through a detour point beside the
fastest route. A route is kept only if it is distinct from those already kept and not much slower
than the fastest. If the rounds run out, the app shows fewer and says so.

## Consequences

- With Mapbox, nearly every trip makes at least one extra request; the number is capped
  (`ROUTE_MAX_EXTRA_REQUESTS`).
- Each route carries a label for how it was found, shown on its card.
- Detour routes can be less natural than a provider's own alternatives; the distinctness and
  slowness limits keep the worst out, and they are tried last.
- The rounds and the distinctness check are provider-independent; an adapter only declares which
  rounds it supports.
