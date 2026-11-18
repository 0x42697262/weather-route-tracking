import type { RouteSummary } from "@/api/types";
import { PERCENT } from "@/constants";
import type { LevelTable } from "@/features/levels/levelTable";
import { levelSegments } from "@/features/routes/levelSegments";
import { formatDistanceKm, type UnitSystem } from "@/lib/units";
import { routeText } from "@/text";
import { swatchStyle } from "@/theme/swatch";

type LevelBarProps = Readonly<{
  summary: RouteSummary;
  levels: LevelTable;
  units: UnitSystem;
}>;

export function LevelBar({ summary, levels, units }: LevelBarProps) {
  const segments = levelSegments(summary, levels);
  const totalKm = segments.reduce((sum, segment) => sum + segment.distanceKm, 0);
  return (
    <div className="flex flex-col gap-1.5">
      <div aria-hidden="true" className="flex h-2.5 w-full overflow-hidden rounded-full bg-muted">
        {segments.map((segment) => (
          <span
            key={segment.key}
            className="h-full"
            style={{ ...swatchStyle(segment.look.colorKey), width: `${(segment.distanceKm / totalKm) * PERCENT}%` }}
          />
        ))}
      </div>
      <ul aria-label={routeText.levelDistances} className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
        {segments.map((segment) => (
          <li key={segment.key} className="flex items-center gap-1" data-color-key={segment.look.colorKey}>
            <span aria-hidden="true" className="size-2.5 rounded-full" style={swatchStyle(segment.look.colorKey)} />
            <span>{segment.look.label}</span>
            <span className="text-muted-foreground tabular-nums">{formatDistanceKm(segment.distanceKm, units)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
