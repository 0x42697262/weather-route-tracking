import { useEffect, useMemo } from "react";
import { useOptions, useTripPlan, useWeatherGrid } from "@/api/queries";
import {
  FIT_BOUNDS_CONTROLS_PX,
  FIT_BOUNDS_PADDING_PX,
  SHEET_HALF_FRACTION,
  WIDE_LANDSCAPE_MEDIA_QUERY,
} from "@/constants";
import { useLevelTable } from "@/features/levels/useLevelTable";
import { CheckpointPopup } from "@/features/map/CheckpointPopup";
import { FitToBounds } from "@/features/map/FitToBounds";
import { HourLayers } from "@/features/map/HourLayers";
import { MapView } from "@/features/map/MapView";
import { useMapData } from "@/features/map/useMapData";
import { usePreferences } from "@/features/preferences/context";
import { MAP_STYLES } from "@/features/preferences/mapStyles";
import { SettingsPopover } from "@/features/preferences/SettingsPopover";
import { routeName, routeNames } from "@/features/routes/routeNames";
import { usePlanArrival } from "@/features/routes/usePlanArrival";
import { VerdictLine } from "@/features/routes/VerdictLine";
import { AppLayout } from "@/features/sheet/AppLayout";
import { panelTitle, usePlanContext } from "@/features/sheet/planContext";
import { TripPanel } from "@/features/sheet/TripPanel";
import type { HeatmapStatus } from "@/features/timeline/heatmapStatus";
import { MapControls } from "@/features/timeline/MapControls";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { useUiActions, useUiState } from "@/state/context";
import { appText, heatmapText } from "@/text";

const ESCAPE_KEY = "Escape";
const KEYDOWN_EVENT = "keydown";

function useHeatmapStatus(): HeatmapStatus {
  const plan = useTripPlan();
  const grid = useWeatherGrid();
  if (plan.data === undefined) {
    return "idle";
  }
  if (grid.isError) {
    return "failed";
  }
  return grid.data === undefined ? "loading" : "ready";
}

function useFitPadding(wide: boolean) {
  return useMemo(
    () => ({
      top: FIT_BOUNDS_PADDING_PX,
      left: FIT_BOUNDS_PADDING_PX,
      right: FIT_BOUNDS_PADDING_PX,
      bottom: wide
        ? FIT_BOUNDS_PADDING_PX + FIT_BOUNDS_CONTROLS_PX
        : window.innerHeight * SHEET_HALF_FRACTION + FIT_BOUNDS_CONTROLS_PX,
    }),
    [wide],
  );
}

export function App() {
  usePlanArrival();
  const preferences = usePreferences();
  const options = useOptions().data;
  const trip = useTripPlan().data;
  const grid = useWeatherGrid().data;
  const levels = useLevelTable();
  const wide = useMediaQuery(WIDE_LANDSCAPE_MEDIA_QUERY);
  const selectedRouteId = useUiState((state) => state.selectedRouteId);
  const storedLayerKey = useUiState((state) => state.heatmapLayerKey);
  const openCheckpointId = useUiState((state) => state.openCheckpointId);
  const panelView = useUiState((state) => state.panelView);
  const { selectRoute, openCheckpoint } = useUiActions();
  const heatmapStatus = useHeatmapStatus();
  const fitPadding = useFitPadding(wide);

  const heatmapLayerKey = storedLayerKey ?? options?.heatmap_layers.default ?? "";
  const names = useMemo(() => routeNames(trip?.routes ?? []), [trip]);
  const planContext = usePlanContext(names);
  const mapData = useMapData({ trip, grid, levels, heatmapLayerKey });
  const openCheckpointRef = openCheckpointId === null ? undefined : mapData.checkpoints.get(openCheckpointId);

  const heatmapChoices = useMemo(
    () =>
      (options?.heatmap_layers.layers ?? []).map((layer) => ({
        value: layer.key,
        label: heatmapText.layers[layer.text_key] ?? layer.key,
      })),
    [options],
  );
  const legendLevels = useMemo(
    () => (levels?.rows ?? []).map((row) => ({ key: row.key, label: row.label, colorKey: row.colorKey })),
    [levels],
  );

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === ESCAPE_KEY) {
        openCheckpoint(null);
      }
    };
    window.addEventListener(KEYDOWN_EVENT, closeOnEscape);
    return () => window.removeEventListener(KEYDOWN_EVENT, closeOnEscape);
  }, [openCheckpoint]);

  return (
    <>
      <title>{appText.documentTitle}</title>
      <AppLayout
        map={
          <MapView
            mapStyleUrl={MAP_STYLES[preferences.mapStyle].url}
            data={mapData.layers}
            selectedRouteId={selectedRouteId}
            heatmapLevelColors={mapData.levelColors}
            attributions={options?.attribution}
            onSelectRoute={selectRoute}
            onOpenCheckpoint={openCheckpoint}
          >
            <HourLayers trip={trip} cellLevels={mapData.cellLevels} selectedRouteId={selectedRouteId} />
            <FitToBounds bounds={mapData.bounds} padding={fitPadding} />
            {openCheckpointRef !== undefined && levels !== null && options !== undefined ? (
              <CheckpointPopup
                checkpoint={openCheckpointRef.checkpoint}
                routeName={routeName(names, openCheckpointRef.routeId)}
                levels={levels}
                variables={options.weather_variables}
                units={preferences.units}
                onClose={() => openCheckpoint(null)}
              />
            ) : null}
          </MapView>
        }
        mapControls={
          <MapControls
            startTimeUtc={trip?.departure_utc ?? null}
            maxHour={options?.forecast_window_hours}
            heatmapLayers={heatmapChoices}
            heatmapLayerKey={heatmapLayerKey}
            heatmapStatus={heatmapStatus}
            legendLevels={legendLevels}
          />
        }
        title={panelTitle(panelView, planContext)}
        headerAction={<SettingsPopover />}
        summary={<VerdictLine />}
        panel={<TripPanel context={planContext} />}
      />
    </>
  );
}
