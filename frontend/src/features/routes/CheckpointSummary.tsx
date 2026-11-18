import type { Checkpoint, WeatherVariableRow } from "@/api/types";
import { checkpointLook, type LevelTable } from "@/features/levels/levelTable";
import { conditionLines, decidedByText } from "@/features/routes/checkpointText";
import { LevelBadge } from "@/features/routes/LevelBadge";
import { formatDateTime } from "@/lib/format";
import { formatDistanceKm, type UnitSystem } from "@/lib/units";
import { routeText } from "@/text";

type CheckpointSummaryProps = Readonly<{
  checkpoint: Checkpoint;
  levels: LevelTable;
  variables: readonly WeatherVariableRow[];
  units: UnitSystem;
}>;

export function CheckpointSummary({ checkpoint, levels, variables, units }: CheckpointSummaryProps) {
  return (
    <div className="flex flex-col gap-1 text-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">
          {routeText.checkpointTitle(checkpoint.index)}{" "}
          <span className="font-normal text-muted-foreground">
            {routeText.atDistance(formatDistanceKm(checkpoint.distance_km, units))}
          </span>
        </span>
        <LevelBadge look={checkpointLook(levels, checkpoint)} />
      </div>
      <span className="tabular-nums">{formatDateTime(checkpoint.arrival_utc)}</span>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 text-xs">
        {conditionLines(checkpoint, variables, units).map((line) => (
          <div key={line.variable} className="contents">
            <dt className="text-muted-foreground">{line.label}</dt>
            <dd className="tabular-nums">{line.value}</dd>
          </div>
        ))}
        <dt className="text-muted-foreground">{routeText.decidedBy}</dt>
        <dd>{checkpoint.on_ferry ? routeText.onFerry : decidedByText(checkpoint)}</dd>
      </dl>
    </div>
  );
}
