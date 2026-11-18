import { useMemo } from "react";
import type { Checkpoint, Trip, WeatherGrid } from "@/api/types";
import { gridCellLevels, gridGeoJson, gridLevelColors, type CellLevels } from "@/features/heatmap/gridGeojson";
import type { LevelTable } from "@/features/levels/levelTable";
import { EMPTY_FEATURE_COLLECTION } from "@/features/map/emptyData";
import { checkpointsGeoJson, stretchesGeoJson, tripBounds, type Bounds } from "@/features/map/geojson";
import type { MapLayerData } from "@/features/map/MapLayers";
import { checkpointId } from "@/features/routes/checkpointText";

const NO_COLORS: readonly string[] = [];
const NO_CELL_LEVELS: CellLevels = [];

export type CheckpointRef = Readonly<{ routeId: string; checkpoint: Checkpoint }>;

export type MapData = Readonly<{
  layers: MapLayerData;
  levelColors: readonly string[];
  cellLevels: CellLevels;
  bounds: Bounds | null;
  checkpoints: ReadonlyMap<string, CheckpointRef>;
}>;

type MapDataInput = Readonly<{
  trip: Trip | undefined;
  grid: WeatherGrid | undefined;
  levels: LevelTable | null;
  heatmapLayerKey: string;
}>;

export function useMapData({ trip, grid, levels, heatmapLayerKey }: MapDataInput): MapData {
  const stretches = useMemo(
    () => (trip === undefined || levels === null ? EMPTY_FEATURE_COLLECTION : stretchesGeoJson(trip, levels)),
    [trip, levels],
  );
  const checkpoints = useMemo(
    () => (trip === undefined || levels === null ? EMPTY_FEATURE_COLLECTION : checkpointsGeoJson(trip, levels)),
    [trip, levels],
  );
  const heatmapData = useMemo(() => (grid === undefined ? EMPTY_FEATURE_COLLECTION : gridGeoJson(grid)), [grid]);
  const cellLevels = useMemo(
    () => (grid === undefined ? NO_CELL_LEVELS : gridCellLevels(grid, heatmapLayerKey)),
    [grid, heatmapLayerKey],
  );
  const levelColors = useMemo(
    () => (grid === undefined || levels === null ? NO_COLORS : gridLevelColors(grid, levels)),
    [grid, levels],
  );
  const bounds = useMemo(() => (trip === undefined ? null : tripBounds(trip)), [trip]);
  const checkpointIndex = useMemo(
    () =>
      new Map(
        (trip?.routes ?? []).flatMap((route) =>
          route.checkpoints.map((checkpoint) => [checkpointId(route.id, checkpoint.index), { routeId: route.id, checkpoint }] as const),
        ),
      ),
    [trip],
  );
  const layers = useMemo(
    () => ({ heatmap: heatmapData, stretches, checkpoints }),
    [heatmapData, stretches, checkpoints],
  );
  return { layers, levelColors, cellLevels, bounds, checkpoints: checkpointIndex };
}
