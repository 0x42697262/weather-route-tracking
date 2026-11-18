import type { Trip } from "@/api/types";
import { worstLevel, type LevelRow, type LevelTable } from "@/features/levels/levelTable";
import { routeName } from "@/features/routes/routeNames";
import { formatDurationS } from "@/lib/format";
import { levelText, verdictText } from "@/text";

export type VerdictInput = Readonly<{
  requested: boolean;
  loading: boolean;
  errorMessage: string | null;
  trip: Trip | undefined;
  names: ReadonlyMap<string, string>;
  levels: LevelTable | null;
  formatDistanceKm: (distanceKm: number) => string;
}>;

export type Verdict = Readonly<{
  text: string;
  level: LevelRow | null;
  recommended: boolean;
}>;

const PLAIN = { level: null, recommended: false } as const;

export function verdictFor(input: VerdictInput): Verdict {
  if (!input.requested) {
    return { text: verdictText.planTrip, ...PLAIN };
  }
  if (input.loading) {
    return { text: verdictText.finding, ...PLAIN };
  }
  if (input.errorMessage !== null) {
    return { text: verdictText.failed(input.errorMessage), ...PLAIN };
  }
  const trip = input.trip;
  if (trip === undefined) {
    return { text: verdictText.finding, ...PLAIN };
  }
  const recommended = trip.routes.find((route) => route.id === trip.recommended_route_id);
  const bestAvailable = trip.routes.find((route) => route.id === trip.best_available_route_id);
  const reason = trip.no_recommendation_reason;
  const shown = recommended ?? bestAvailable;
  if (shown === undefined || (recommended === undefined && reason === null)) {
    return { text: reason === null ? verdictText.planTrip : verdictText.noRecommendation[reason], ...PLAIN };
  }
  const level = input.levels === null ? null : worstLevel(input.levels, shown.summary);
  const lead =
    recommended === undefined && reason !== null
      ? [verdictText.bestAvailablePrefix[reason], verdictText.bestAvailable(routeName(input.names, shown.id))]
      : [verdictText.take(routeName(input.names, shown.id))];
  const parts = [
    ...lead,
    ...(level === null ? [] : [levelText.riskSuffix(level.label)]),
    formatDurationS(shown.summary.travel_time_s),
    ...(shown.summary.unknown_km > 0 ? [verdictText.unknownPart(input.formatDistanceKm(shown.summary.unknown_km))] : []),
  ];
  return { text: parts.join(verdictText.separator), level, recommended: recommended !== undefined };
}
