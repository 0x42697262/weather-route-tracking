import type { Checkpoint, RiskLevel, RiskLevelRow, RouteSummary, StretchKind } from "@/api/types";
import { levelText } from "@/text";
import { FERRY_COLOR_KEY, UNKNOWN_COLOR_KEY, isColorKey, type ColorKey } from "@/theme/colors";

export type LevelRow = Readonly<{
  key: RiskLevel;
  score: number;
  label: string;
  colorKey: ColorKey;
  blocksRecommendation: boolean;
}>;

export type LevelTable = Readonly<{
  rows: readonly LevelRow[];
  byKey: ReadonlyMap<string, LevelRow>;
}>;

export type LevelLook = Readonly<{
  label: string;
  colorKey: ColorKey;
}>;

export const UNKNOWN_LOOK: LevelLook = { label: levelText.unknown, colorKey: UNKNOWN_COLOR_KEY };
export const FERRY_LOOK: LevelLook = { label: levelText.ferry, colorKey: FERRY_COLOR_KEY };

const STRETCH_KIND_LOOKS: Readonly<Record<StretchKind, LevelLook>> = {
  rated: UNKNOWN_LOOK,
  unknown: UNKNOWN_LOOK,
  ferry: FERRY_LOOK,
};

export function buildLevelTable(riskLevels: readonly RiskLevelRow[]): LevelTable {
  const rows = [...riskLevels]
    .sort((left, right) => left.score - right.score)
    .map(
      (row): LevelRow => ({
        key: row.key,
        score: row.score,
        label: levelText.levels[row.key],
        colorKey: isColorKey(row.color_key) ? row.color_key : UNKNOWN_COLOR_KEY,
        blocksRecommendation: row.blocks_recommendation,
      }),
    );
  return { rows, byKey: new Map(rows.map((row) => [row.key, row])) };
}

export function levelLook(table: LevelTable, level: RiskLevel | null, fallback: LevelLook): LevelLook {
  return (level === null ? undefined : table.byKey.get(level)) ?? fallback;
}

export function stretchLook(table: LevelTable, level: RiskLevel | null, kind: StretchKind): LevelLook {
  return levelLook(table, level, STRETCH_KIND_LOOKS[kind]);
}

export function checkpointLook(table: LevelTable, checkpoint: Checkpoint): LevelLook {
  return levelLook(table, checkpoint.level, checkpoint.on_ferry ? FERRY_LOOK : UNKNOWN_LOOK);
}

export function worstLevel(table: LevelTable, summary: RouteSummary): LevelRow | null {
  return summary.worst_level === null ? null : (table.byKey.get(summary.worst_level) ?? null);
}
