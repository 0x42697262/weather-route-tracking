import { useEffect, useRef } from "react";
import { useMap, type PaddingOptions } from "react-map-gl/maplibre";
import { FIT_BOUNDS_DURATION_MS } from "@/constants";
import type { Bounds } from "@/features/map/geojson";

type FitToBoundsProps = Readonly<{
  bounds: Bounds | null;
  padding: PaddingOptions;
}>;

export function FitToBounds({ bounds, padding }: FitToBoundsProps) {
  const { current: map } = useMap();
  const paddingRef = useRef(padding);
  useEffect(() => {
    paddingRef.current = padding;
  }, [padding]);
  useEffect(() => {
    if (map === undefined || bounds === null) {
      return;
    }
    const [southWest, northEast] = bounds;
    map.fitBounds([southWest[0], southWest[1], northEast[0], northEast[1]], {
      padding: paddingRef.current,
      duration: FIT_BOUNDS_DURATION_MS,
    });
  }, [map, bounds]);
  return null;
}
