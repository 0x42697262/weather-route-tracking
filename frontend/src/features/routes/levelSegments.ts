import type { RouteSummary } from "@/api/types";
import { FERRY_LOOK, UNKNOWN_LOOK, type LevelLook, type LevelTable } from "@/features/levels/levelTable";

export type Segment = Readonly<{ key: string; look: LevelLook; distanceKm: number }>;

export function levelSegments(summary: RouteSummary, levels: LevelTable): readonly Segment[] {
  const rated = levels.rows.map((row) => ({
    key: row.key,
    look: row,
    distanceKm: summary.distance_km_by_level[row.key] ?? 0,
  }));
  const extra = [
    { key: UNKNOWN_LOOK.colorKey, look: UNKNOWN_LOOK, distanceKm: summary.unknown_km },
    { key: FERRY_LOOK.colorKey, look: FERRY_LOOK, distanceKm: summary.ferry_km },
  ];
  return [...rated, ...extra].filter((segment) => segment.distanceKm > 0);
}
