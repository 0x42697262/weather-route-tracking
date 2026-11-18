import type { Feature, FeatureCollection, LineString, Point, Position } from "geojson";
import type { Trip } from "@/api/types";
import { checkpointLook, stretchLook, type LevelTable } from "@/features/levels/levelTable";
import { checkpointId } from "@/features/routes/checkpointText";
import { FEATURE_PROPERTIES } from "@/keys";
import { decodePolyline } from "@/lib/polyline";

export type Bounds = readonly [readonly [number, number], readonly [number, number]];

const LONGITUDE = 0;
const LATITUDE = 1;

function collection<Geometry extends LineString | Point>(features: Feature<Geometry>[]): FeatureCollection<Geometry> {
  return { type: "FeatureCollection", features };
}

export function stretchesGeoJson(trip: Trip, levels: LevelTable): FeatureCollection<LineString> {
  return collection(
    trip.routes.flatMap((route) =>
      route.stretches.map(
        (stretch): Feature<LineString> => ({
          type: "Feature",
          geometry: { type: "LineString", coordinates: decodePolyline(stretch.polyline) },
          properties: {
            [FEATURE_PROPERTIES.routeId]: route.id,
            [FEATURE_PROPERTIES.colorKey]: stretchLook(levels, stretch.level, stretch.kind).colorKey,
          },
        }),
      ),
    ),
  );
}

export function checkpointsGeoJson(trip: Trip, levels: LevelTable): FeatureCollection<Point> {
  return collection(
    trip.routes.flatMap((route) =>
      route.checkpoints.map(
        (checkpoint): Feature<Point> => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: [checkpoint.longitude, checkpoint.latitude] },
          properties: {
            [FEATURE_PROPERTIES.routeId]: route.id,
            [FEATURE_PROPERTIES.checkpointId]: checkpointId(route.id, checkpoint.index),
            [FEATURE_PROPERTIES.colorKey]: checkpointLook(levels, checkpoint).colorKey,
          },
        }),
      ),
    ),
  );
}

export function trucksGeoJson(trip: Trip, hour: number): FeatureCollection<Point> {
  return collection(
    trip.routes.flatMap((route) => {
      const position = route.positions_by_hour.find((entry) => entry.hour === hour);
      if (position === undefined) {
        return [];
      }
      const feature: Feature<Point> = {
        type: "Feature",
        geometry: { type: "Point", coordinates: [position.longitude, position.latitude] },
        properties: { [FEATURE_PROPERTIES.routeId]: route.id },
      };
      return [feature];
    }),
  );
}

export function boundsOf(positions: readonly Position[]): Bounds | null {
  if (positions.length === 0) {
    return null;
  }
  let west = Number.POSITIVE_INFINITY;
  let south = Number.POSITIVE_INFINITY;
  let east = Number.NEGATIVE_INFINITY;
  let north = Number.NEGATIVE_INFINITY;
  for (const position of positions) {
    const longitude = position[LONGITUDE] ?? 0;
    const latitude = position[LATITUDE] ?? 0;
    west = Math.min(west, longitude);
    east = Math.max(east, longitude);
    south = Math.min(south, latitude);
    north = Math.max(north, latitude);
  }
  return [
    [west, south],
    [east, north],
  ];
}

export function tripBounds(trip: Trip): Bounds | null {
  return boundsOf(trip.routes.flatMap((route) => decodePolyline(route.polyline)));
}
