import { describe, expect, it } from "vitest";
import {
  COLOR_MATCH,
  checkpointLayers,
  dimmedRouteLayers,
  heatmapLayers,
  selectedRouteLayers,
} from "@/features/map/layers";
import { PATTERN_IMAGES, hatchImageId, hatchPatternImage, hexToRgb } from "@/features/map/patternImages";

describe("map layers", () => {
  it("colors features from every token, falling back to unknown", () => {
    expect(COLOR_MATCH).toEqual([
      "match",
      ["get", "color_key"],
      "risk-low",
      "#4A7BB7",
      "risk-moderate",
      "#FDB366",
      "risk-high",
      "#F67E4B",
      "risk-severe",
      "#DD3D2D",
      "risk-no-travel",
      "#A50026",
      "risk-unknown",
      "#8C8C8C",
      "ferry",
      "#4B5563",
      "#8C8C8C",
    ]);
  });

  it("keeps the same layer ids when the selected route changes", () => {
    const ids = (routeId: string | null) =>
      [...dimmedRouteLayers(routeId), ...selectedRouteLayers(routeId), ...checkpointLayers(routeId)].map(
        (layer) => layer.id,
      );
    expect(ids("route-a")).toEqual(ids("route-b"));
    expect(ids(null)).toEqual(ids("route-a"));
  });

  it("splits route lines by line style with one layer each", () => {
    expect(dimmedRouteLayers(null).map((layer) => layer.id)).toEqual([
      "routes-dimmed-solid",
      "routes-dimmed-dashed",
      "routes-dimmed-hatched",
    ]);
  });

  it("filters the selected route by its id", () => {
    const [casing] = selectedRouteLayers("route-b");
    expect(casing?.filter).toEqual(["==", ["get", "route_id"], "route-b"]);
  });

  it("colors heatmap cells by the level index in their feature state", () => {
    const [solid] = heatmapLayers(["#111111", "#222222"]);
    expect(solid?.paint?.["fill-color"]).toEqual([
      "match",
      ["coalesce", ["feature-state", "level"], -1],
      0,
      "#111111",
      1,
      "#222222",
      "rgba(0, 0, 0, 0)",
    ]);
  });

  it("hatches heatmap cells with no level for the hour", () => {
    const hatched = heatmapLayers(["#111111"])[1];
    expect(hatched?.paint).toMatchObject({
      "fill-pattern": "pattern-hatch-risk-unknown",
      "fill-opacity": ["case", ["==", ["coalesce", ["feature-state", "level"], -1], -1], 0.45, 0],
    });
  });
});

describe("pattern images", () => {
  it("parses hex colors", () => {
    expect(hexToRgb("#4A7BB7")).toEqual([74, 123, 183]);
  });

  it("builds an opaque square RGBA image", () => {
    const image = hatchPatternImage("#8C8C8C");
    expect(image.data).toHaveLength(image.width * image.height * 4);
    expect(image.data[3]).toBe(255);
    expect([...image.data.slice(0, 3)]).toEqual([140, 140, 140]);
  });

  it("registers one image per hatched color key", () => {
    expect([...PATTERN_IMAGES.keys()]).toEqual([hatchImageId("risk-unknown")]);
  });
});
