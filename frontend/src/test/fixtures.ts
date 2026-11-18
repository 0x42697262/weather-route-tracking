import type { Checkpoint, Options, Route, RouteSummary, Trip, WeatherGrid } from "@/api/types";

export const OPTIONS: Options = {
  rule_set_version: 1,
  forecast_window_hours: 48,
  stretch_method: "worse_end",
  routes_target: 3,
  departure_window: { past_tolerance_minutes: 15, max_hours_ahead: 96 },
  attribution: [{ text: "Weather data by Open-Meteo.com", url: "https://open-meteo.com/" }],
  options: {
    checkpoint_spacing: {
      name: "checkpoint_spacing",
      tier: "basic",
      text_key: "checkpoint_spacing",
      available: true,
      unit: "km",
      choices: [
        { value: 10, unit: "mi", km: 16.09344 },
        { value: 25, unit: "mi", km: 40.2336 },
        { value: 50, unit: "mi", km: 80.4672 },
      ],
      default: { value: 25, unit: "mi", km: 40.2336 },
    },
    include_rest_stops: {
      name: "include_rest_stops",
      tier: "advanced",
      text_key: "include_rest_stops",
      available: true,
      default: true,
    },
    load_weight: {
      name: "load_weight",
      tier: "basic",
      text_key: "load_weight",
      available: true,
      unit: "kg",
      required: true,
      default: null,
      minimum: 0,
      maximum: 50000,
    },
  },
  risk_levels: [
    { key: "low", score: 0, ranked: false, blocks_recommendation: false, text_key: "low", color_key: "risk-low" },
    { key: "moderate", score: 1, ranked: false, blocks_recommendation: false, text_key: "moderate", color_key: "risk-moderate" },
    { key: "high", score: 2, ranked: true, blocks_recommendation: false, text_key: "high", color_key: "risk-high" },
    { key: "severe", score: 3, ranked: true, blocks_recommendation: false, text_key: "severe", color_key: "risk-severe" },
    { key: "no_travel", score: 4, ranked: true, blocks_recommendation: true, text_key: "no_travel", color_key: "risk-no-travel" },
  ],
  weather_variables: [
    { key: "wind_speed", metric_unit: "km/h", text_key: "wind_speed" },
    { key: "rain_rate", metric_unit: "mm/h", text_key: "rain_rate" },
    { key: "snowfall_rate", metric_unit: "cm/h", text_key: "snowfall_rate" },
  ],
  heatmap_layers: {
    default: "risk",
    layers: [
      { key: "risk", variable: null, text_key: "combined_risk" },
      { key: "wind_speed", variable: "wind_speed", text_key: "wind_speed" },
    ],
  },
};

const DEPARTURE_UTC = "2026-11-17T21:00:00Z";

export function summary(change: Partial<RouteSummary> = {}): RouteSummary {
  return {
    distance_km_by_level: { low: 100, moderate: 50, high: 0, severe: 0, no_travel: 0 },
    unknown_km: 0,
    ferry_km: 0,
    total_km: 150,
    worst_level: "moderate",
    blocking_km: 0,
    average_risk: 0.33,
    blocked: false,
    driving_s: 19200,
    rest_s: 0,
    ferry_s: 0,
    travel_time_s: 19200,
    arrival_utc: "2026-11-18T02:20:00Z",
    warnings: [],
    ...change,
  };
}

export function checkpoint(change: Partial<Checkpoint> = {}): Checkpoint {
  return {
    index: 0,
    distance_km: 0,
    latitude: 32.7767,
    longitude: -96.797,
    arrival_utc: DEPARTURE_UTC,
    values: { wind_speed: 20, rain_rate: 0, snowfall_rate: 0 },
    level: "low",
    weather_level: "low",
    decided_by: null,
    conditions: [],
    on_ferry: false,
    ...change,
  };
}

export function route(change: Partial<Route> = {}): Route {
  return {
    id: "route-1",
    rank: 1,
    recommended: true,
    not_recommendable_reason: null,
    source: "fastest",
    distance_km: 150,
    polyline: "_p~iF~ps|U_ulLnnqC",
    summary: summary(),
    checkpoints: [checkpoint(), checkpoint({ index: 1, distance_km: 150, latitude: 40.7, longitude: -120.95, level: "moderate", decided_by: "band:wind_speed" })],
    stretches: [
      { start_km: 0, end_km: 100, level: "low", kind: "rated", polyline: "_p~iF~ps|U_ulLnnqC" },
      { start_km: 100, end_km: 150, level: null, kind: "unknown", polyline: "_ulLnnqC_mqNvxq`@" },
      { start_km: 150, end_km: 160, level: null, kind: "ferry", polyline: "_ulLnnqC_mqNvxq`@" },
    ],
    stops: [],
    positions_by_hour: [
      { hour: 0, distance_km: 0, latitude: 32.7767, longitude: -96.797 },
      { hour: 1, distance_km: 80, latitude: 33.5, longitude: -97 },
    ],
    refined_samples: 0,
    ...change,
  };
}

export function trip(change: Partial<Trip> = {}): Trip {
  const routes = change.routes ?? [
    route(),
    route({ id: "route-2", rank: 2, recommended: false, source: "alternative", summary: summary({ travel_time_s: 21000 }) }),
  ];
  return {
    rule_set_version: 1,
    stretch_method: "worse_end",
    departure_utc: DEPARTURE_UTC,
    vehicle_weight_kg: 32885,
    options_used: { checkpoint_spacing_km: 40.2336, include_rest_stops: true, load_kg: 18143.69 },
    routes,
    ranking: { key_names: [], keys: [] },
    recommended_route_id: "route-1",
    no_recommendation_reason: null,
    routes_requested: 3,
    routes_found: routes.length,
    fewer_routes_than_requested: routes.length < 3,
    rounds_tried: ["fastest"],
    warnings: routes.length < 3 ? ["fewer_routes_than_target"] : [],
    weather: { cell_size_deg: 0.1, cells_requested: 10, cells_missing: 0, unknown_checkpoints: 0, refined_samples: 0 },
    ...change,
  };
}

export const GRID: WeatherGrid = {
  rule_set_version: 1,
  departure_utc: DEPARTURE_UTC,
  hours_utc: [DEPARTURE_UTC, "2026-11-17T22:00:00Z"],
  cell_size_deg: 0.2,
  levels: ["low", "moderate", "high", "severe", "no_travel"],
  latitudes: [32.8, 33],
  longitudes: [-96.8, -97],
  layers: [
    { key: "risk", variable: null, text_key: "combined_risk", levels: [[0, 1], [4, null]], values: null },
    { key: "wind_speed", variable: "wind_speed", text_key: "wind_speed", levels: [[2, 2], [3, 3]], values: [[40, 41], [60, 61]] },
  ],
  cells_missing: 0,
};
