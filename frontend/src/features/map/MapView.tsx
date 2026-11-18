import type { ReactNode } from "react";
import Map, { AttributionControl, type MapEvent, type MapLayerMouseEvent } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Attribution } from "@/api/types";
import { INITIAL_MAP_VIEW } from "@/constants";
import { INTERACTIVE_LAYER_IDS } from "@/features/map/layers";
import { MapLayers, type MapLayerData } from "@/features/map/MapLayers";
import { attributionHtml } from "@/features/map/attribution";
import { PATTERN_IMAGES } from "@/features/map/patternImages";
import { FEATURE_PROPERTIES, OPEN_METEO_URL } from "@/keys";
import { appText } from "@/text";

const MAP_FILL_STYLE = { width: "100%", height: "100%" } as const;
const ATTRIBUTION_POSITION = "top-right";
const ATTRIBUTION_SEPARATOR = "|";
const FALLBACK_ATTRIBUTIONS: readonly Attribution[] = [{ text: appText.openMeteoAttribution, url: OPEN_METEO_URL }];

type MapViewProps = Readonly<{
  mapStyleUrl: string;
  data: MapLayerData;
  selectedRouteId: string | null;
  heatmapLevelColors: readonly string[];
  attributions: readonly Attribution[] | undefined;
  onSelectRoute: (routeId: string) => void;
  onOpenCheckpoint: (checkpointId: string) => void;
  children?: ReactNode;
}>;

function registerPatternImages(event: MapEvent): void {
  const map = event.target;
  map.setMissingStyleImageResolver((imageId) => {
    const image = PATTERN_IMAGES.get(imageId);
    if (image !== undefined && !map.hasImage(imageId)) {
      map.addImage(imageId, image());
    }
  });
}

function stringProperty(properties: Record<string, unknown> | null | undefined, name: string): string | null {
  const value = properties?.[name];
  return typeof value === "string" ? value : null;
}

export function MapView({
  mapStyleUrl,
  data,
  selectedRouteId,
  heatmapLevelColors,
  attributions,
  onSelectRoute,
  onOpenCheckpoint,
  children,
}: MapViewProps) {
  const customAttribution = (attributions ?? FALLBACK_ATTRIBUTIONS).map(attributionHtml);

  const handleClick = (event: MapLayerMouseEvent) => {
    for (const feature of event.features ?? []) {
      const checkpoint = stringProperty(feature.properties, FEATURE_PROPERTIES.checkpointId);
      if (checkpoint !== null) {
        onOpenCheckpoint(checkpoint);
        return;
      }
      const routeId = stringProperty(feature.properties, FEATURE_PROPERTIES.routeId);
      if (routeId !== null) {
        onSelectRoute(routeId);
        return;
      }
    }
  };

  return (
    <section aria-label={appText.mapLabel} className="relative h-full w-full">
      <Map
        initialViewState={INITIAL_MAP_VIEW}
        mapStyle={mapStyleUrl}
        attributionControl={false}
        style={MAP_FILL_STYLE}
        onLoad={registerPatternImages}
        interactiveLayerIds={INTERACTIVE_LAYER_IDS}
        onClick={handleClick}
      >
        <AttributionControl
          key={customAttribution.join(ATTRIBUTION_SEPARATOR)}
          position={ATTRIBUTION_POSITION}
          compact={false}
          customAttribution={customAttribution}
        />
        <MapLayers data={data} selectedRouteId={selectedRouteId} heatmapLevelColors={heatmapLevelColors} />
        {children}
      </Map>
    </section>
  );
}
