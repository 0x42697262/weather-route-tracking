import { Route as RouteIcon } from "lucide-react";
import { useMemo } from "react";
import { useTripPlan } from "@/api/queries";
import { useLevelTable } from "@/features/levels/useLevelTable";
import { usePreferences } from "@/features/preferences/context";
import { formatDistanceKm } from "@/lib/units";
import { routeNames } from "@/features/routes/routeNames";
import { verdictFor, type Verdict } from "@/features/routes/verdict";
import { TEST_IDS } from "@/keys";
import { useUiState } from "@/state/context";
import { LEVEL_ICONS } from "@/theme/icons";
import { cssVariableReference } from "@/theme/colors";

export function VerdictLine() {
  const requested = useUiState((state) => state.tripRequest !== null);
  const plan = useTripPlan();
  const levels = useLevelTable();
  const { units } = usePreferences();
  const names = useMemo(() => routeNames(plan.data?.routes ?? []), [plan.data]);
  const verdict = verdictFor({
    requested,
    loading: plan.isFetching,
    errorMessage: plan.error?.message ?? null,
    trip: plan.data,
    names,
    levels,
    formatDistanceKm: (distanceKm) => formatDistanceKm(distanceKm, units),
  });
  return <VerdictView verdict={verdict} />;
}

export function VerdictView({ verdict }: Readonly<{ verdict: Verdict }>) {
  const Icon = verdict.level === null ? RouteIcon : LEVEL_ICONS[verdict.level.colorKey];
  return (
    <p
      role="status"
      data-testid={TEST_IDS.verdict}
      className="flex min-h-11 items-center gap-2 text-base leading-tight font-semibold"
    >
      <span
        aria-hidden="true"
        className="flex size-8 shrink-0 items-center justify-center rounded-full border-[3px] border-muted bg-background text-foreground"
        style={verdict.level === null ? undefined : { borderColor: cssVariableReference(verdict.level.colorKey) }}
      >
        <Icon className="size-4" />
      </span>
      <span>{verdict.text}</span>
    </p>
  );
}
