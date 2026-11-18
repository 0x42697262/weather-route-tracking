import { describe, expect, it } from "vitest";
import { gridCellLevels, gridGeoJson, gridLevelColors } from "@/features/heatmap/gridGeojson";
import { buildLevelTable } from "@/features/levels/levelTable";
import { checkpointsGeoJson, stretchesGeoJson, tripBounds, trucksGeoJson } from "@/features/map/geojson";
import { GRID, OPTIONS, trip } from "@/test/fixtures";

const LEVELS = buildLevelTable(OPTIONS.risk_levels);

describe("route GeoJSON", () => {
  it("draws every stretch with its route and color key, unknown and ferry by kind", () => {
    const stretches = stretchesGeoJson(trip(), LEVELS);
    expect(stretches.features).toHaveLength(6);
    expect(stretches.features.slice(0, 3).map((feature) => feature.properties)).toEqual([
      { route_id: "route-1", color_key: "risk-low" },
      { route_id: "route-1", color_key: "risk-unknown" },
      { route_id: "route-1", color_key: "ferry" },
    ]);
    expect(stretches.features[0]?.geometry.coordinates).toEqual([
      [-120.2, 38.5],
      [-120.95, 40.7],
    ]);
  });

  it("gives every checkpoint an id and its level color", () => {
    const checkpoints = checkpointsGeoJson(trip(), LEVELS);
    expect(checkpoints.features[1]?.properties).toEqual({
      route_id: "route-1",
      checkpoint_id: "route-1#1",
      color_key: "risk-moderate",
    });
    expect(checkpoints.features[1]?.geometry.coordinates).toEqual([-120.95, 40.7]);
  });

  it("places each truck at the server's position for the hour", () => {
    const trucks = trucksGeoJson(trip(), 1);
    expect(trucks.features.map((feature) => feature.geometry.coordinates)).toEqual([
      [-97, 33.5],
      [-97, 33.5],
    ]);
    expect(trucksGeoJson(trip(), 9).features).toHaveLength(0);
  });

  it("bounds every route line", () => {
    expect(tripBounds(trip())).toEqual([
      [-120.95, 38.5],
      [-120.2, 40.7],
    ]);
  });
});

describe("heatmap GeoJSON", () => {
  it("builds one square per cell, identified by its index", () => {
    const grid = gridGeoJson(GRID);
    expect(grid.features).toHaveLength(2);
    expect(grid.features.map((feature) => feature.id)).toEqual([0, 1]);
    expect(grid.features[0]?.geometry.coordinates[0]?.[0]?.map((value) => Number(value.toFixed(6)))).toEqual([
      -96.9, 32.7,
    ]);
  });

  it("lists every cell's level index per hour, -1 where there is no forecast", () => {
    expect(gridCellLevels(GRID, "risk")).toEqual([
      [0, 1],
      [4, -1],
    ]);
    expect(gridCellLevels(GRID, "wind_speed")).toEqual([
      [2, 2],
      [3, 3],
    ]);
  });

  it("colors level indexes from the level table", () => {
    expect(gridLevelColors(GRID, LEVELS)).toEqual(["#4A7BB7", "#FDB366", "#F67E4B", "#DD3D2D", "#A50026"]);
  });
});
