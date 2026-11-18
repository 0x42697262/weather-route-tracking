import type { JSX } from "react";
import { RouteDetails } from "@/features/routes/RouteDetails";
import { RouteList } from "@/features/routes/RouteList";
import { routeName } from "@/features/routes/routeNames";
import { TripForm } from "@/features/trip-form/TripForm";
import type { PlanContext } from "@/features/sheet/planContext";
import { useUiActions, useUiState } from "@/state/context";
import type { PanelView } from "@/state/uiStore";

function RoutesView({ context }: Readonly<{ context: PlanContext }>) {
  const { selectRoute, showRouteDetails, showPanel, submitTrip } = useUiActions();
  return (
    <RouteList
      trip={context.trip}
      request={context.request}
      options={context.options}
      names={context.names}
      selectedRouteId={context.selectedRouteId}
      levels={context.levels}
      units={context.units}
      onSelect={selectRoute}
      onShowDetails={showRouteDetails}
      onEditTrip={() => showPanel("form", "full")}
      onReplan={submitTrip}
    />
  );
}

function DetailsView({ context }: Readonly<{ context: PlanContext }>) {
  const { showPanel } = useUiActions();
  const route =
    context.trip.routes.find((candidate) => candidate.id === context.selectedRouteId) ?? context.trip.routes[0];
  if (route === undefined) {
    return <RoutesView context={context} />;
  }
  return (
    <RouteDetails
      trip={context.trip}
      route={route}
      name={routeName(context.names, route.id)}
      options={context.options}
      levels={context.levels}
      units={context.units}
      onBack={() => showPanel("routes", "half")}
    />
  );
}

const PLAN_VIEWS: Readonly<Record<PanelView, ((props: Readonly<{ context: PlanContext }>) => JSX.Element) | null>> = {
  form: null,
  routes: RoutesView,
  details: DetailsView,
};

export function TripPanel({ context }: Readonly<{ context: PlanContext | null }>) {
  const view = useUiState((state) => state.panelView);
  const View = PLAN_VIEWS[view];
  if (context === null || View === null) {
    return <TripForm />;
  }
  return <View context={context} />;
}
