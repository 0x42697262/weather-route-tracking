import { useMemo } from "react";
import { useOptions } from "@/api/queries";
import { buildLevelTable, type LevelTable } from "@/features/levels/levelTable";

export function useLevelTable(): LevelTable | null {
  const riskLevels = useOptions().data?.risk_levels;
  return useMemo(() => (riskLevels === undefined ? null : buildLevelTable(riskLevels)), [riskLevels]);
}
