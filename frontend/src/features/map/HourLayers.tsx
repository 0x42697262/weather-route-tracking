import { useMemo } from "react";
import { Layer, Source } from "react-map-gl/maplibre";
import type { Trip } from "@/api/types";
import type { CellLevels } from "@/features/heatmap/gridGeojson";
import { HeatmapHourState } from "@/features/heatmap/HeatmapHourState";
import { EMPTY_FEATURE_COLLECTION } from "@/features/map/emptyData";
import { trucksGeoJson } from "@/features/map/geojson";
import { truckLayer } from "@/features/map/layers";
import { MAP_SOURCE_IDS } from "@/keys";
import { useUiState } from "@/state/context";

type HourLayersProps = Readonly<{
  trip: Trip | undefined;
  cellLevels: CellLevels;
  selectedRouteId: string | null;
}>;

export function HourLayers({ trip, cellLevels, selectedRouteId }: HourLayersProps) {
  const hour = useUiState((state) => state.sliderHour);
  const trucks = useMemo(
    () => (trip === undefined ? EMPTY_FEATURE_COLLECTION : trucksGeoJson(trip, hour)),
    [trip, hour],
  );
  const truck = useMemo(() => truckLayer(selectedRouteId), [selectedRouteId]);
  return (
    <>
      <HeatmapHourState cellLevels={cellLevels} hour={hour} />
      <Source id={MAP_SOURCE_IDS.trucks} type="geojson" data={trucks}>
        <Layer {...truck} />
      </Source>
    </>
  );
}
