import type {
  CircleLayerSpecification,
  FillLayerSpecification,
  LineLayerSpecification,
} from "react-map-gl/maplibre";
import { MAP_PAINT, NO_LEVEL_INDEX, ROUTE_HIT_WIDTH_PX, DIMMED_TRUCK_OPACITY } from "@/constants";
import { hatchImageId } from "@/features/map/patternImages";
import { FEATURE_PROPERTIES, HEATMAP_LEVEL_STATE, MAP_IMAGE_PREFIXES, MAP_LAYER_IDS } from "@/keys";
import {
  COLOR_KEYS,
  LINE_STYLES,
  MAP_COLORS,
  UNKNOWN_COLOR_KEY,
  colorHex,
  colorKeysWithLineStyle,
  type LineStyle,
} from "@/theme/colors";

type Without<Spec> = Omit<Spec, "source">;
export type FillLayer = Without<FillLayerSpecification>;
export type LineLayer = Without<LineLayerSpecification>;
export type CircleLayer = Without<CircleLayerSpecification>;
type Filter = NonNullable<LineLayerSpecification["filter"]>;
type LinePaint = NonNullable<LineLayerSpecification["paint"]>;

const NO_ROUTE_ID = "";

const colorKeyValue = ["get", FEATURE_PROPERTIES.colorKey] as const;
const routeIdValue = ["get", FEATURE_PROPERTIES.routeId] as const;

export const COLOR_MATCH = [
  "match",
  colorKeyValue,
  ...COLOR_KEYS.flatMap((key) => [key, colorHex(key)]),
  colorHex(UNKNOWN_COLOR_KEY),
] as unknown as NonNullable<LinePaint["line-color"]>;

const HATCH_PATTERN = ["concat", MAP_IMAGE_PREFIXES.hatch, colorKeyValue] as unknown as NonNullable<
  LinePaint["line-pattern"]
>;

export function lineStyleFilter(lineStyle: LineStyle): Filter {
  return ["in", colorKeyValue, ["literal", [...colorKeysWithLineStyle(lineStyle)]]] as unknown as Filter;
}

export function routeFilter(selectedRouteId: string | null, selected: boolean): Filter {
  return [selected ? "==" : "!=", routeIdValue, selectedRouteId ?? NO_ROUTE_ID] as unknown as Filter;
}

function allOf(...filters: Filter[]): Filter {
  return ["all", ...filters] as unknown as Filter;
}

const LINE_STYLE_PAINT: Readonly<Record<LineStyle, LinePaint>> = {
  solid: { "line-color": COLOR_MATCH },
  dashed: { "line-color": COLOR_MATCH, "line-dasharray": [...MAP_PAINT.routeDashPattern] },
  hatched: { "line-pattern": HATCH_PATTERN },
};

const LINE_LAYOUT = { "line-cap": "round", "line-join": "round" } as const;

export function styledLayerId(baseId: string, lineStyle: LineStyle): string {
  return `${baseId}-${lineStyle}`;
}

const TRANSPARENT = "rgba(0, 0, 0, 0)";
const UNKNOWN_HATCH_IMAGE = hatchImageId(UNKNOWN_COLOR_KEY);

type FillPaint = NonNullable<FillLayerSpecification["paint"]>;

const HEATMAP_LEVEL = ["coalesce", ["feature-state", HEATMAP_LEVEL_STATE], NO_LEVEL_INDEX];

export function heatmapLayers(levelColors: readonly string[]): readonly FillLayer[] {
  const levelIndex = HEATMAP_LEVEL;
  const colorMatch = (
    levelColors.length === 0
      ? TRANSPARENT
      : ["match", levelIndex, ...levelColors.flatMap((hex, index) => [index, hex]), TRANSPARENT]
  ) as unknown as NonNullable<FillPaint["fill-color"]>;
  const hatchOpacity = [
    "case",
    ["==", levelIndex, NO_LEVEL_INDEX],
    MAP_PAINT.heatmapOpacity,
    0,
  ] as unknown as NonNullable<FillPaint["fill-opacity"]>;
  return [
    {
      id: styledLayerId(MAP_LAYER_IDS.heatmap, "solid"),
      type: "fill",
      paint: { "fill-color": colorMatch, "fill-opacity": MAP_PAINT.heatmapOpacity, "fill-antialias": false },
    },
    {
      id: styledLayerId(MAP_LAYER_IDS.heatmap, "hatched"),
      type: "fill",
      paint: { "fill-pattern": UNKNOWN_HATCH_IMAGE, "fill-opacity": hatchOpacity, "fill-antialias": false },
    },
  ];
}

export const ROUTE_HIT_LAYER: LineLayer = {
  id: MAP_LAYER_IDS.routesHit,
  type: "line",
  layout: { "line-cap": "round", "line-join": "round" },
  paint: { "line-color": MAP_COLORS.truckFill, "line-width": ROUTE_HIT_WIDTH_PX, "line-opacity": 0 },
};

export function dimmedRouteLayers(selectedRouteId: string | null): readonly LineLayer[] {
  return LINE_STYLES.map((lineStyle) => ({
    id: styledLayerId(MAP_LAYER_IDS.routesDimmed, lineStyle),
    type: "line",
    filter: allOf(routeFilter(selectedRouteId, false), lineStyleFilter(lineStyle)),
    layout: LINE_LAYOUT,
    paint: {
      ...LINE_STYLE_PAINT[lineStyle],
      "line-width": MAP_PAINT.dimmedRouteWidthPx,
      "line-opacity": MAP_PAINT.dimmedRouteOpacity,
    },
  }));
}

export function selectedRouteLayers(selectedRouteId: string | null): readonly LineLayer[] {
  const casing: LineLayer = {
    id: MAP_LAYER_IDS.routeSelectedCasing,
    type: "line",
    filter: routeFilter(selectedRouteId, true),
    layout: LINE_LAYOUT,
    paint: {
      "line-color": MAP_COLORS.selectedRouteCasing,
      "line-width": MAP_PAINT.selectedRouteCasingWidthPx,
    },
  };
  const styled = LINE_STYLES.map(
    (lineStyle): LineLayer => ({
      id: styledLayerId(MAP_LAYER_IDS.routeSelected, lineStyle),
      type: "line",
      filter: allOf(routeFilter(selectedRouteId, true), lineStyleFilter(lineStyle)),
      layout: LINE_LAYOUT,
      paint: { ...LINE_STYLE_PAINT[lineStyle], "line-width": MAP_PAINT.selectedRouteWidthPx },
    }),
  );
  return [casing, ...styled];
}

const CHECKPOINT_PAINT = {
  "circle-color": COLOR_MATCH,
  "circle-radius": MAP_PAINT.checkpointRadiusPx,
  "circle-stroke-color": MAP_COLORS.checkpointStroke,
  "circle-stroke-width": MAP_PAINT.checkpointStrokeWidthPx,
} as unknown as NonNullable<CircleLayerSpecification["paint"]>;

export function checkpointLayers(selectedRouteId: string | null): readonly CircleLayer[] {
  return [
    {
      id: MAP_LAYER_IDS.checkpointsAll,
      type: "circle",
      minzoom: MAP_PAINT.allCheckpointsMinZoom,
      filter: routeFilter(selectedRouteId, false),
      paint: CHECKPOINT_PAINT,
    },
    {
      id: MAP_LAYER_IDS.checkpointsSelected,
      type: "circle",
      filter: routeFilter(selectedRouteId, true),
      paint: CHECKPOINT_PAINT,
    },
  ];
}

export function truckLayer(selectedRouteId: string | null): CircleLayer {
  return {
    id: MAP_LAYER_IDS.trucks,
    type: "circle",
    paint: {
      "circle-opacity": [
        "case",
        ["==", routeIdValue, selectedRouteId ?? NO_ROUTE_ID],
        1,
        DIMMED_TRUCK_OPACITY,
      ] as unknown as number,
      "circle-stroke-opacity": [
        "case",
        ["==", routeIdValue, selectedRouteId ?? NO_ROUTE_ID],
        1,
        DIMMED_TRUCK_OPACITY,
      ] as unknown as number,
      "circle-color": MAP_COLORS.truckFill,
    "circle-radius": MAP_PAINT.truckRadiusPx,
    "circle-stroke-color": MAP_COLORS.truckStroke,
    "circle-stroke-width": MAP_PAINT.truckStrokeWidthPx,
    },
  };
}

export const INTERACTIVE_LAYER_IDS = [
  MAP_LAYER_IDS.checkpointsSelected,
  MAP_LAYER_IDS.checkpointsAll,
  MAP_LAYER_IDS.routesHit,
];
