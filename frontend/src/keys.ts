export const ROOT_ELEMENT_ID = "root";

export const PREFERENCES_STORAGE_KEY = "weather-routes.preferences";

export const OPEN_METEO_URL = "https://open-meteo.com/";

export const CLIENT_ERROR_CODES = {
  unexpected: "unexpected_response",
  network: "network_error",
} as const;

export const SWIPE_IGNORE_ATTRIBUTE = "data-base-ui-swipe-ignore";

export const FEATURE_PROPERTIES = {
  routeId: "route_id",
  colorKey: "color_key",
  checkpointId: "checkpoint_id",
} as const;

export const MAP_IMAGE_PREFIXES = {
  hatch: "pattern-hatch-",
} as const;

export const MAP_SOURCE_IDS = {
  heatmap: "heatmap",
  stretches: "stretches",
  checkpoints: "checkpoints",
  trucks: "trucks",
} as const;

export const MAP_LAYER_IDS = {
  heatmap: "heatmap",
  routesHit: "routes-hit",
  routesDimmed: "routes-dimmed",
  routeSelectedCasing: "route-selected-casing",
  routeSelected: "route-selected",
  checkpointsAll: "checkpoints-all",
  checkpointsSelected: "checkpoints-selected",
  trucks: "trucks",
} as const;

export const QUERY_KEYS = {
  options: "options",
  placeSuggestions: "place-suggestions",
  place: "place",
  trip: "trip",
  weatherGrid: "weather-grid",
} as const;

export const API_PATH_SEPARATOR = ".";
export const HEATMAP_LEVEL_STATE = "level";
export const DECIDED_BY_SEPARATOR = ":";
export const CHECKPOINT_ID_SEPARATOR = "#";

export const ELEMENT_IDS = {
  tripForm: "trip-form",
  origin: "trip-origin",
  destination: "trip-destination",
  departure: "trip-departure",
  loadWeight: "trip-load-weight",
  spacing: "trip-spacing",
  restStops: "trip-rest-stops",
} as const;

export const TEST_IDS = {
  verdict: "verdict-line",
  routeCard: "route-card",
  notRecommendable: "not-recommendable",
  heatmapStatus: "heatmap-status",
} as const;
