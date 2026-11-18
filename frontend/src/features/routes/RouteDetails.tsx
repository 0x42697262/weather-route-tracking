import { ChevronLeft, Coffee, TriangleAlert } from "lucide-react";
import type { Options, Route, Trip } from "@/api/types";
import { Button } from "@/components/ui/button";
import { type LevelTable } from "@/features/levels/levelTable";
import { CheckpointSummary } from "@/features/routes/CheckpointSummary";
import { LevelBar } from "@/features/routes/LevelBar";
import { formatDateTime, formatDurationS } from "@/lib/format";
import { formatDistanceKm, formatMassKg, type UnitSystem } from "@/lib/units";
import { routeText } from "@/text";

type RouteDetailsProps = Readonly<{
  trip: Trip;
  route: Route;
  name: string;
  options: Options;
  levels: LevelTable;
  units: UnitSystem;
  onBack: () => void;
}>;

export function RouteDetails({ trip, route, name, options, levels, units, onBack }: RouteDetailsProps) {
  const summary = route.summary;
  const distances = {
    unknown: formatDistanceKm(summary.unknown_km, units),
    ferry: formatDistanceKm(summary.ferry_km, units),
    blocking: formatDistanceKm(summary.blocking_km, units),
  };
  return (
    <article aria-label={name} className="flex flex-col gap-4">
      <Button type="button" variant="ghost" className="min-h-11 self-start px-2" onClick={onBack}>
        <ChevronLeft aria-hidden="true" />
        {routeText.backToRoutes}
      </Button>
      <h3 className="flex items-baseline gap-2 text-lg font-semibold">
        {name}
        <span className="text-sm font-normal text-muted-foreground">
          {routeText.rank(route.rank)} · {routeText.sources[route.source]}
        </span>
      </h3>
      <dl className="grid grid-cols-3 gap-2 text-sm">
        <div>
          <dt className="text-xs text-muted-foreground">{routeText.travelTime}</dt>
          <dd className="font-semibold tabular-nums">{formatDurationS(summary.travel_time_s)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">{routeText.distance}</dt>
          <dd className="font-semibold tabular-nums">{formatDistanceKm(summary.total_km, units)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">{routeText.arrival}</dt>
          <dd className="font-semibold tabular-nums">{formatDateTime(summary.arrival_utc)}</dd>
        </div>
      </dl>
      <LevelBar summary={summary} levels={levels} units={units} />
      {summary.warnings.length > 0 ? (
        <ul className="flex flex-col gap-1 text-sm">
          {summary.warnings.map((warning) => (
            <li key={warning} className="flex items-start gap-1.5 text-destructive">
              <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              <span>{routeText.warnings[warning](distances)}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <section className="flex flex-col gap-2">
        <h3 className="text-base font-semibold">{routeText.checkpoints}</h3>
        <ol className="flex flex-col divide-y rounded-xl border">
          {route.checkpoints.map((checkpoint) => (
            <li key={checkpoint.index} className="px-3 py-2">
              <CheckpointSummary
                checkpoint={checkpoint}
                levels={levels}
                variables={options.weather_variables}
                units={units}
              />
            </li>
          ))}
        </ol>
      </section>
      {route.stops.length > 0 ? (
        <section className="flex flex-col gap-2">
          <h3 className="text-base font-semibold">{routeText.stops}</h3>
          <ol className="flex flex-col gap-1.5 text-sm">
            {route.stops.map((stop) => (
              <li key={stop.start_utc} className="flex items-start gap-2">
                <Coffee aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                <span>
                  {routeText.stopLine(
                    routeText.stopKinds[stop.kind],
                    formatDateTime(stop.start_utc),
                    formatDurationS(stop.duration_s),
                  )}
                </span>
              </li>
            ))}
          </ol>
          <p className="text-xs text-muted-foreground">{routeText.restAssumptions}</p>
        </section>
      ) : null}
      <section className="flex flex-col gap-1 text-xs text-muted-foreground">
        <h3 className="text-sm font-semibold text-foreground">{routeText.basis}</h3>
        <p>{routeText.ruleSetVersion(trip.rule_set_version)}</p>
        <p>{routeText.spacingUsed(formatDistanceKm(trip.options_used.checkpoint_spacing_km, units))}</p>
        <p>{routeText.loadUsed(formatMassKg(trip.options_used.load_kg, units))}</p>
        <p>{routeText.restUsed(trip.options_used.include_rest_stops)}</p>
      </section>
    </article>
  );
}
