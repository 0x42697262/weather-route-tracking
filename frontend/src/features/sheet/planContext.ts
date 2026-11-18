import { useOptions, useTripPlan } from "@/api/queries";
import type { Options, Trip, TripRequest } from "@/api/types";
import type { LevelTable } from "@/features/levels/levelTable";
import { useLevelTable } from "@/features/levels/useLevelTable";
import { usePreferences } from "@/features/preferences/context";
import { routeName } from "@/features/routes/routeNames";
import type { UnitSystem } from "@/lib/units";
import { useUiState } from "@/state/context";
import type { PanelView } from "@/state/uiStore";
import { sheetText } from "@/text";

export type PlanContext = Readonly<{
  trip: Trip;
  request: TripRequest;
  options: Options;
  levels: LevelTable;
  units: UnitSystem;
  names: ReadonlyMap<string, string>;
  selectedRouteId: string | null;
}>;

export function panelTitle(view: PanelView, context: PlanContext | null): string {
  if (context === null) {
    return sheetText.planTrip;
  }
  const titles: Readonly<Record<PanelView, string>> = {
    form: sheetText.planTrip,
    routes: sheetText.routes,
    details: routeName(context.names, context.selectedRouteId ?? ""),
  };
  return titles[view];
}

export function usePlanContext(names: ReadonlyMap<string, string>): PlanContext | null {
  const trip = useTripPlan().data;
  const options = useOptions().data;
  const levels = useLevelTable();
  const request = useUiState((state) => state.tripRequest);
  const selectedRouteId = useUiState((state) => state.selectedRouteId);
  const { units } = usePreferences();
  if (trip === undefined || options === undefined || levels === null || request === null) {
    return null;
  }
  return { trip, request, options, levels, units, names, selectedRouteId };
}
