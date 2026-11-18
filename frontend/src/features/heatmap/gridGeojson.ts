import type { FeatureCollection, Polygon } from "geojson";
import type { WeatherGrid } from "@/api/types";
import { NO_LEVEL_INDEX } from "@/constants";
import type { LevelTable } from "@/features/levels/levelTable";
import { colorHex, UNKNOWN_COLOR_KEY } from "@/theme/colors";

const HALF = 0.5;

export type CellLevels = readonly (readonly number[])[];

export function gridGeoJson(grid: WeatherGrid): FeatureCollection<Polygon> {
  const halfSizeDeg = grid.cell_size_deg * HALF;
  return {
    type: "FeatureCollection",
    features: grid.latitudes.map((latitude, cell) => {
      const longitude = grid.longitudes[cell] ?? 0;
      const west = longitude - halfSizeDeg;
      const east = longitude + halfSizeDeg;
      const south = latitude - halfSizeDeg;
      const north = latitude + halfSizeDeg;
      return {
        type: "Feature",
        id: cell,
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [west, south],
              [east, south],
              [east, north],
              [west, north],
              [west, south],
            ],
          ],
        },
        properties: {},
      };
    }),
  };
}

export function gridCellLevels(grid: WeatherGrid, layerKey: string): CellLevels {
  const layer = grid.layers.find((candidate) => candidate.key === layerKey) ?? grid.layers[0];
  return grid.latitudes.map((_, cell) => {
    const levelsByHour = layer?.levels[cell] ?? [];
    return grid.hours_utc.map((_hour, hour) => levelsByHour[hour] ?? NO_LEVEL_INDEX);
  });
}

export function gridLevelColors(grid: WeatherGrid, levels: LevelTable): readonly string[] {
  return grid.levels.map((level) => colorHex(levels.byKey.get(level)?.colorKey ?? UNKNOWN_COLOR_KEY));
}
