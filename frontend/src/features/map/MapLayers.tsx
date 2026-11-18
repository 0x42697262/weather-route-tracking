import type { FeatureCollection } from "geojson";
import { useMemo } from "react";
import { Layer, Source } from "react-map-gl/maplibre";
import {
  ROUTE_HIT_LAYER,
  checkpointLayers,
  dimmedRouteLayers,
  heatmapLayers,
  selectedRouteLayers,
} from "@/features/map/layers";
import { MAP_SOURCE_IDS } from "@/keys";

export type MapLayerData = Readonly<{
  heatmap: FeatureCollection;
  stretches: FeatureCollection;
  checkpoints: FeatureCollection;
}>;

type MapLayersProps = Readonly<{
  data: MapLayerData;
  selectedRouteId: string | null;
  heatmapLevelColors: readonly string[];
}>;

export function MapLayers({ data, selectedRouteId, heatmapLevelColors }: MapLayersProps) {
  const routeLayers = useMemo(
    () => [...dimmedRouteLayers(selectedRouteId), ...selectedRouteLayers(selectedRouteId)],
    [selectedRouteId],
  );
  const pointLayers = useMemo(() => checkpointLayers(selectedRouteId), [selectedRouteId]);
  const gridLayers = useMemo(() => heatmapLayers(heatmapLevelColors), [heatmapLevelColors]);

  return (
    <>
      <Source id={MAP_SOURCE_IDS.heatmap} type="geojson" data={data.heatmap}>
        {gridLayers.map((layer) => (
          <Layer key={layer.id} {...layer} />
        ))}
      </Source>
      <Source id={MAP_SOURCE_IDS.stretches} type="geojson" data={data.stretches}>
        <Layer {...ROUTE_HIT_LAYER} />
        {routeLayers.map((layer) => (
          <Layer key={layer.id} {...layer} />
        ))}
      </Source>
      <Source id={MAP_SOURCE_IDS.checkpoints} type="geojson" data={data.checkpoints}>
        {pointLayers.map((layer) => (
          <Layer key={layer.id} {...layer} />
        ))}
      </Source>
    </>
  );
}
