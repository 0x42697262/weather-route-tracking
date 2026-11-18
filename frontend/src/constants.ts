export const INITIAL_MAP_VIEW = {
  longitude: -98.5795,
  latitude: 39.8283,
  zoom: 3.5,
} as const;

export const DISPLAY_LOCALE = "en-US";

export const KM_PER_MILE = 1.609344;
export const MM_PER_INCH = 25.4;
export const CM_PER_INCH = 2.54;
export const KG_PER_POUND = 0.45359237;
export const METRIC_FACTOR = 1;

export const SECONDS_PER_MINUTE = 60;
export const MINUTES_PER_HOUR = 60;
export const SECONDS_PER_HOUR = SECONDS_PER_MINUTE * MINUTES_PER_HOUR;
export const MS_PER_SECOND = 1000;
export const MS_PER_HOUR = SECONDS_PER_HOUR * MS_PER_SECOND;

export const DEFAULT_FORECAST_HOURS = 48;
export const SLIDER_STEP_HOURS = 1;

export const PREFERENCES_SCHEMA_VERSION = 1;

export const SIDE_PANEL_MIN_WIDTH_PX = 900;
export const WIDE_LANDSCAPE_MEDIA_QUERY = `(min-width: ${SIDE_PANEL_MIN_WIDTH_PX}px) and (orientation: landscape)`;

export const SHEET_PEEK_HEIGHT_PX = 148;
export const SHEET_HALF_FRACTION = 0.5;
export const SHEET_FULL_FRACTION = 0.92;

export const HATCH_ANGLE_DEG = 45;
export const HATCH_STRIPE_PX = 3;
export const DASH_LENGTH_PX = 6;
export const HATCH_PERIOD_PX = 6;
export const DASH_PERIOD_PX = 12;
export const HATCH_PATTERN_SIZE_PX = 8;
export const HATCH_PATTERN_STRIPE_PX = 2;
export const RGBA_CHANNELS = 4;
export const OPAQUE_ALPHA = 255;
export const HEX_RADIX = 16;
export const HEX_CHANNEL_LENGTH = 2;

export const ROUTE_DASH_ON_WIDTHS = 2;
export const ROUTE_DASH_OFF_WIDTHS = 1.5;

export const MAP_PAINT = {
  heatmapOpacity: 0.45,
  dimmedRouteWidthPx: 3,
  dimmedRouteOpacity: 0.55,
  selectedRouteWidthPx: 6,
  selectedRouteCasingWidthPx: 9,
  routeDashPattern: [ROUTE_DASH_ON_WIDTHS, ROUTE_DASH_OFF_WIDTHS],
  checkpointRadiusPx: 5,
  checkpointStrokeWidthPx: 1.5,
  allCheckpointsMinZoom: 9,
  truckRadiusPx: 8,
  truckStrokeWidthPx: 2,
} as const;

export const PLACE_QUERY_MIN_CHARS = 3;
export const PLACE_SEARCH_DEBOUNCE_MS = 250;
export const OPTIONS_STALE_TIME_MINUTES = 5;
export const OPTIONS_STALE_TIME_MS = OPTIONS_STALE_TIME_MINUTES * SECONDS_PER_MINUTE * MS_PER_SECOND;
export const SERVER_DATA_STALE_TIME_MS = Number.POSITIVE_INFINITY;

export const POLYLINE_PRECISION = 5;
export const POLYLINE_CHUNK_BITS = 5;
export const POLYLINE_CHUNK_MASK = 0x1f;
export const POLYLINE_CONTINUATION_BIT = 0x20;
export const POLYLINE_ASCII_OFFSET = 63;
export const DECIMAL_BASE = 10;

export const NO_LEVEL_INDEX = -1;

export const ROUTE_HIT_WIDTH_PX = 24;
export const DIMMED_TRUCK_OPACITY = 0.55;

export const FIT_BOUNDS_PADDING_PX = 48;
export const FIT_BOUNDS_CONTROLS_PX = 150;
export const FIT_BOUNDS_DURATION_MS = 600;

export const ROUTE_LETTER_CODE_START = 65;
export const PERCENT = 100;
export const LOAD_INPUT_STEP = 1;
export const NOW_REFRESH_S = 30;
export const NOW_REFRESH_MS = NOW_REFRESH_S * MS_PER_SECOND;
