import type { TripRequest } from "@/api/types";
import { EMPTY_TRIP_DRAFT, type TripDraft } from "@/features/trip-form/draft";
import type { SheetHeight } from "@/features/sheet/sheetHeights";

export const PANEL_VIEWS = ["form", "routes", "details"] as const;

export type PanelView = (typeof PANEL_VIEWS)[number];

export type UiState = Readonly<{
  sheetHeight: SheetHeight;
  panelView: PanelView;
  selectedRouteId: string | null;
  sliderHour: number;
  heatmapLayerKey: string | null;
  openCheckpointId: string | null;
  draft: TripDraft;
  tripRequest: TripRequest | null;
}>;

export const INITIAL_UI_STATE: UiState = Object.freeze({
  sheetHeight: "full",
  panelView: "form",
  selectedRouteId: null,
  sliderHour: 0,
  heatmapLayerKey: null,
  openCheckpointId: null,
  draft: EMPTY_TRIP_DRAFT,
  tripRequest: null,
});

export type UiActions = Readonly<{
  setSheetHeight: (sheetHeight: SheetHeight) => void;
  showPanel: (panelView: PanelView, sheetHeight?: SheetHeight) => void;
  selectRoute: (routeId: string | null) => void;
  showRouteDetails: (routeId: string) => void;
  setSliderHour: (hour: number) => void;
  setHeatmapLayer: (layerKey: string | null) => void;
  openCheckpoint: (checkpointId: string | null) => void;
  updateDraft: (change: Partial<TripDraft>) => void;
  submitTrip: (request: TripRequest) => void;
  showPlan: (recommendedRouteId: string | null) => void;
}>;

export type UiStore = Readonly<{
  getSnapshot: () => UiState;
  subscribe: (listener: () => void) => () => void;
  actions: UiActions;
}>;

export function createUiStore(initial: UiState = INITIAL_UI_STATE): UiStore {
  let current = initial;
  const listeners = new Set<() => void>();

  const set = (change: Partial<UiState>) => {
    const next = Object.freeze({ ...current, ...change });
    const changed = (Object.keys(change) as (keyof UiState)[]).some(
      (key) => next[key] !== current[key],
    );
    if (!changed) {
      return;
    }
    current = next;
    for (const listener of listeners) {
      listener();
    }
  };

  return Object.freeze({
    getSnapshot: () => current,
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    actions: Object.freeze({
      setSheetHeight: (sheetHeight: SheetHeight) => set({ sheetHeight }),
      showPanel: (panelView: PanelView, sheetHeight?: SheetHeight) =>
        set(sheetHeight === undefined ? { panelView } : { panelView, sheetHeight }),
      selectRoute: (selectedRouteId: string | null) => set({ selectedRouteId, openCheckpointId: null }),
      showRouteDetails: (selectedRouteId: string) =>
        set({ selectedRouteId, panelView: "details", sheetHeight: "full", openCheckpointId: null }),
      setSliderHour: (sliderHour: number) => set({ sliderHour }),
      setHeatmapLayer: (heatmapLayerKey: string | null) => set({ heatmapLayerKey }),
      openCheckpoint: (openCheckpointId: string | null) => set({ openCheckpointId }),
      updateDraft: (change: Partial<TripDraft>) =>
        set({ draft: Object.freeze({ ...current.draft, ...change }) }),
      submitTrip: (tripRequest: TripRequest) => set({ tripRequest }),
      showPlan: (recommendedRouteId: string | null) =>
        set({
          selectedRouteId: recommendedRouteId,
          panelView: "routes",
          sheetHeight: "half",
          sliderHour: 0,
          openCheckpointId: null,
        }),
    }),
  });
}
