import type { Checkpoint, WeatherVariable, WeatherVariableRow } from "@/api/types";
import { CHECKPOINT_ID_SEPARATOR, DECIDED_BY_SEPARATOR } from "@/keys";
import { formatMetricUnitValue, type UnitSystem } from "@/lib/units";
import { routeText, variableText } from "@/text";

export function checkpointId(routeId: string, index: number): string {
  return `${routeId}${CHECKPOINT_ID_SEPARATOR}${index}`;
}

export function variableLabel(variable: string): string {
  return Object.hasOwn(variableText, variable) ? variableText[variable as WeatherVariable] : variable;
}

export function decidedByText(checkpoint: Pick<Checkpoint, "decided_by" | "level" | "on_ferry">): string {
  if (checkpoint.decided_by === null) {
    return checkpoint.level === null ? routeText.decidedByUnknown : routeText.decidedByNothing;
  }
  const [kind = "", variable = ""] = checkpoint.decided_by.split(DECIDED_BY_SEPARATOR);
  const describe = routeText.decidedByKinds[kind];
  return describe === undefined ? checkpoint.decided_by : describe(variableLabel(variable));
}

export type ConditionLine = Readonly<{ variable: string; label: string; value: string }>;

export function conditionLines(
  checkpoint: Checkpoint,
  variables: readonly WeatherVariableRow[],
  units: UnitSystem,
): readonly ConditionLine[] {
  return variables.map((row) => {
    const value = checkpoint.values[row.key] ?? null;
    return {
      variable: row.key,
      label: variableLabel(row.key),
      value: value === null ? routeText.noValue : formatMetricUnitValue(value, row.metric_unit, units),
    };
  });
}
