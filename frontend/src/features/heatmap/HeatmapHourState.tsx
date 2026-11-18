import { useEffect } from "react";
import { useMap } from "react-map-gl/maplibre";
import { NO_LEVEL_INDEX } from "@/constants";
import type { CellLevels } from "@/features/heatmap/gridGeojson";
import { HEATMAP_LEVEL_STATE, MAP_SOURCE_IDS } from "@/keys";

type HeatmapHourStateProps = Readonly<{
  cellLevels: CellLevels;
  hour: number;
}>;

export function HeatmapHourState({ cellLevels, hour }: HeatmapHourStateProps) {
  const { current: map } = useMap();
  useEffect(() => {
    if (map === undefined || map.getSource(MAP_SOURCE_IDS.heatmap) === undefined) {
      return;
    }
    cellLevels.forEach((levelsByHour, cell) => {
      map.setFeatureState(
        { source: MAP_SOURCE_IDS.heatmap, id: cell },
        { [HEATMAP_LEVEL_STATE]: levelsByHour[hour] ?? NO_LEVEL_INDEX },
      );
    });
  }, [map, cellLevels, hour]);
  return null;
}
