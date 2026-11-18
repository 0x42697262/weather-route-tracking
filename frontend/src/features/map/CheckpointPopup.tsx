import { Popup } from "react-map-gl/maplibre";
import type { Checkpoint, WeatherVariableRow } from "@/api/types";
import type { LevelTable } from "@/features/levels/levelTable";
import { CheckpointSummary } from "@/features/routes/CheckpointSummary";
import type { UnitSystem } from "@/lib/units";

type CheckpointPopupProps = Readonly<{
  checkpoint: Checkpoint;
  routeName: string;
  levels: LevelTable;
  variables: readonly WeatherVariableRow[];
  units: UnitSystem;
  onClose: () => void;
}>;

const POPUP_MAX_WIDTH = "18rem";

export function CheckpointPopup({ checkpoint, routeName, levels, variables, units, onClose }: CheckpointPopupProps) {
  return (
    <Popup
      longitude={checkpoint.longitude}
      latitude={checkpoint.latitude}
      onClose={onClose}
      closeOnClick={false}
      maxWidth={POPUP_MAX_WIDTH}
      focusAfterOpen={false}
    >
      <div className="flex flex-col gap-1 pr-4 text-foreground">
        <span className="text-xs text-muted-foreground">{routeName}</span>
        <CheckpointSummary checkpoint={checkpoint} levels={levels} variables={variables} units={units} />
      </div>
    </Popup>
  );
}
