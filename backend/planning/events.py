"""Log event names of planning services (`docs/trip-planning.md`, `docs/risk-model.md`).

Adapter events (`upstream.*`, `weather.*`) are in `planning/adapters/events.py`.
"""

TRIP_REQUESTED = "trip.requested"
TRIP_REJECTED = "trip.rejected"
TRIP_PLANNED = "trip.planned"
ROUTES_FETCHED = "routes.fetched"
ROUTES_REJECTED = "routes.rejected"
ROUTES_ROUND_SKIPPED = "routes.round_skipped"
ROUTES_FALLBACK_KEPT = "routes.fallback_kept"
CHECKPOINT_CLASSIFIED = "checkpoint.classified"
REFINE_SAMPLED = "refine.sampled"
ROUTE_SUMMARIZED = "route.summarized"
ROUTES_RANKED = "routes.ranked"
RECOMMENDATION_NONE = "recommendation.none"
GRID_REQUESTED = "grid.requested"
GRID_REJECTED = "grid.rejected"
GRID_BUILT = "grid.built"
