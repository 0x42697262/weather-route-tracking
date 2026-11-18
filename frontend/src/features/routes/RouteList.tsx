import { Info, Pencil } from "lucide-react";
import type { Options, Trip, TripRequest } from "@/api/types";
import { Button } from "@/components/ui/button";
import type { LevelTable } from "@/features/levels/levelTable";
import { RouteCard } from "@/features/routes/RouteCard";
import { CustomOptionsNotice } from "@/features/trip-form/CustomOptionsNotice";
import { requestWithDefaultOptions, tripUsesCustomOptions } from "@/features/trip-form/draft";
import type { UnitSystem } from "@/lib/units";
import { routeText, sheetText } from "@/text";

type RouteListProps = Readonly<{
  trip: Trip;
  request: TripRequest;
  options: Options;
  names: ReadonlyMap<string, string>;
  selectedRouteId: string | null;
  levels: LevelTable;
  units: UnitSystem;
  onSelect: (routeId: string) => void;
  onShowDetails: (routeId: string) => void;
  onEditTrip: () => void;
  onReplan: (request: TripRequest) => void;
}>;

export function RouteList({
  trip,
  request,
  options,
  names,
  selectedRouteId,
  levels,
  units,
  onSelect,
  onShowDetails,
  onEditTrip,
  onReplan,
}: RouteListProps) {
  const context = { routesFound: trip.routes_found };
  return (
    <section aria-label={sheetText.routes} className="flex flex-col gap-3">
      {trip.warnings.length > 0 ? (
        <ul className="flex flex-col gap-1.5">
          {trip.warnings.map((warning) => (
            <li key={warning} className="flex items-start gap-2 rounded-lg bg-muted px-3 py-2 text-sm">
              <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              <span>{routeText.tripWarnings[warning](context)}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {tripUsesCustomOptions(trip, options) ? (
        <CustomOptionsNotice onReset={() => onReplan(requestWithDefaultOptions(request))} />
      ) : null}
      <ol className="flex flex-col gap-3">
        {trip.routes.map((route) => (
          <RouteCard
            key={route.id}
            route={route}
            name={names.get(route.id) ?? route.id}
            selected={route.id === selectedRouteId}
            levels={levels}
            units={units}
            onSelect={() => onSelect(route.id)}
            onShowDetails={() => onShowDetails(route.id)}
          />
        ))}
      </ol>
      <Button type="button" variant="outline" className="min-h-11" onClick={onEditTrip}>
        <Pencil aria-hidden="true" />
        {routeText.editTrip}
      </Button>
    </section>
  );
}
