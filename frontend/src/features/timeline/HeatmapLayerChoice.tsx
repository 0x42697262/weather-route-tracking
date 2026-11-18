import { LoaderCircle, Palette } from "lucide-react";
import { ChoiceGroup, type Choice } from "@/components/ChoiceGroup";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTitle, PopoverTrigger } from "@/components/ui/popover";
import { Legend, type LegendLevel } from "@/features/legend/Legend";
import type { HeatmapStatus } from "@/features/timeline/heatmapStatus";
import { TEST_IDS } from "@/keys";
import { heatmapText } from "@/text";


type StatusInfo = Readonly<{ hint: string | null; enabled: boolean; busy: boolean }>;

const STATUS_INFO: Readonly<Record<HeatmapStatus, StatusInfo>> = {
  idle: { hint: heatmapText.unavailableHint, enabled: false, busy: false },
  loading: { hint: heatmapText.loading, enabled: false, busy: true },
  failed: { hint: heatmapText.failed, enabled: false, busy: false },
  ready: { hint: null, enabled: true, busy: false },
};

type HeatmapLayerChoiceProps = Readonly<{
  layers: readonly Choice<string>[];
  value: string | null;
  status: HeatmapStatus;
  legendLevels: readonly LegendLevel[];
  onChange: (layerKey: string) => void;
}>;

export function HeatmapLayerChoice({ layers, value, status, legendLevels, onChange }: HeatmapLayerChoiceProps) {
  const info = STATUS_INFO[status];
  return (
    <div className="flex flex-col gap-1" data-testid={TEST_IDS.heatmapStatus} data-status={status}>
      <div className="flex items-center gap-1.5">
        {layers.length > 0 ? (
          <ChoiceGroup
            label={heatmapText.label}
            choices={layers}
            value={value}
            onChange={onChange}
            disabled={!info.enabled}
          />
        ) : null}
        {legendLevels.length > 0 ? (
          <Popover>
            <PopoverTrigger
              render={
                <Button variant="outline" size="icon" className="size-11 shrink-0" aria-label={heatmapText.legend} />
              }
            >
              <Palette className="size-5" />
            </PopoverTrigger>
            <PopoverContent align="end" side="top" className="w-56">
              <PopoverTitle className="text-sm font-medium">{heatmapText.legend}</PopoverTitle>
              <Legend levels={legendLevels} />
            </PopoverContent>
          </Popover>
        ) : null}
      </div>
      {info.hint === null ? null : (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          {info.busy ? <LoaderCircle aria-hidden="true" className="size-3.5 animate-spin" /> : null}
          {info.hint}
        </p>
      )}
    </div>
  );
}
