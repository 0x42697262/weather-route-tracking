import { ChevronRight, TriangleAlert } from "lucide-react";
import type { Route } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { type LevelTable } from "@/features/levels/levelTable";
import { LevelBar } from "@/features/routes/LevelBar";
import { TEST_IDS } from "@/keys";
import { formatDurationS, formatTime } from "@/lib/format";
import { formatDistanceKm, type UnitSystem } from "@/lib/units";
import { cn } from "@/lib/utils";
import { routeText } from "@/text";

type RouteCardProps = Readonly<{
  route: Route;
  name: string;
  selected: boolean;
  levels: LevelTable;
  units: UnitSystem;
  onSelect: () => void;
  onShowDetails: () => void;
}>;

export function RouteCard({ route, name, selected, levels, units, onSelect, onShowDetails }: RouteCardProps) {
  const summary = route.summary;
  const distances = {
    unknown: formatDistanceKm(summary.unknown_km, units),
    ferry: formatDistanceKm(summary.ferry_km, units),
    blocking: formatDistanceKm(summary.blocking_km, units),
  };
  return (
    <li
      data-testid={TEST_IDS.routeCard}
      data-route-id={route.id}
      className={cn(
        "flex flex-col gap-2 rounded-xl border bg-card p-3 text-card-foreground transition-colors",
        selected ? "border-foreground ring-1 ring-foreground" : "border-border",
      )}
    >
      <button
        type="button"
        aria-pressed={selected}
        onClick={onSelect}
        className="flex min-h-11 flex-col gap-2 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <span className="flex items-center gap-2">
          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-foreground text-sm font-semibold text-background tabular-nums">
            {routeText.rank(route.rank)}
          </span>
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="truncate font-semibold">{name}</span>
            <span className="truncate text-xs text-muted-foreground">{routeText.sources[route.source]}</span>
          </span>
          {route.recommended ? <Badge>{routeText.recommended}</Badge> : null}
          {route.best_available ? <Badge variant="destructive">{routeText.bestAvailable}</Badge> : null}
        </span>
        <span className="flex items-baseline gap-3 text-sm">
          <span className="text-lg font-semibold tabular-nums">{formatDurationS(summary.travel_time_s)}</span>
          <span className="text-muted-foreground tabular-nums">{formatDistanceKm(summary.total_km, units)}</span>
          <span className="ml-auto text-xs text-muted-foreground">
            {routeText.arrival} {formatTime(summary.arrival_utc)}
          </span>
        </span>
      </button>
      <LevelBar summary={summary} levels={levels} units={units} />
      {summary.rest_s > 0 ? (
        <p className="text-xs text-muted-foreground">{routeText.restAdded(formatDurationS(summary.rest_s))}</p>
      ) : null}
      {route.not_recommendable_reason === null ? null : (
        <p data-testid={TEST_IDS.notRecommendable} className="text-xs font-medium text-muted-foreground">
          {routeText.notRecommendable[route.not_recommendable_reason]}
        </p>
      )}
      {summary.warnings.length > 0 ? (
        <ul className="flex flex-col gap-1 text-xs">
          {summary.warnings.map((warning) => (
            <li key={warning} className="flex items-start gap-1.5 text-destructive">
              <TriangleAlert aria-hidden="true" className="mt-px size-3.5 shrink-0" />
              <span>{routeText.warnings[warning](distances)}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <Button
        type="button"
        variant="ghost"
        className="min-h-11 justify-between self-stretch"
        onClick={onShowDetails}
        aria-label={routeText.showDetails(name)}
      >
        {routeText.details}
        <ChevronRight aria-hidden="true" />
      </Button>
    </li>
  );
}
