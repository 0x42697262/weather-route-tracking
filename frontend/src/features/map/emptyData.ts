import type { FeatureCollection } from "geojson";
import type { MapLayerData } from "@/features/map/MapLayers";

export const EMPTY_FEATURE_COLLECTION: FeatureCollection = Object.freeze({
  type: "FeatureCollection",
  features: [],
});

export const EMPTY_MAP_LAYER_DATA: MapLayerData = Object.freeze({
  heatmap: EMPTY_FEATURE_COLLECTION,
  stretches: EMPTY_FEATURE_COLLECTION,
  checkpoints: EMPTY_FEATURE_COLLECTION,
});
