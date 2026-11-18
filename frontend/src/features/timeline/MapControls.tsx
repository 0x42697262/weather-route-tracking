import type { Choice } from "@/components/ChoiceGroup";
import type { LegendLevel } from "@/features/legend/Legend";
import { HeatmapLayerChoice } from "@/features/timeline/HeatmapLayerChoice";
import type { HeatmapStatus } from "@/features/timeline/heatmapStatus";
import { TimeSlider } from "@/features/timeline/TimeSlider";
import { SWIPE_IGNORE_ATTRIBUTE } from "@/keys";
import { cn } from "@/lib/utils";
import { useUiActions, useUiState } from "@/state/context";

type MapControlsProps = Readonly<{
  startTimeUtc: string | null;
  maxHour?: number;
  heatmapLayers: readonly Choice<string>[];
  heatmapLayerKey: string | null;
  heatmapStatus: HeatmapStatus;
  legendLevels: readonly LegendLevel[];
  className?: string;
}>;

const SWIPE_IGNORE_PROPS = { [SWIPE_IGNORE_ATTRIBUTE]: "" };

export function MapControls({
  startTimeUtc,
  maxHour,
  heatmapLayers,
  heatmapLayerKey,
  heatmapStatus,
  legendLevels,
  className,
}: MapControlsProps) {
  const sliderHour = useUiState((state) => state.sliderHour);
  const { setSliderHour, setHeatmapLayer } = useUiActions();

  return (
    <div
      {...SWIPE_IGNORE_PROPS}
      className={cn(
        "pointer-events-auto flex flex-col gap-2 rounded-xl bg-background/95 p-3 shadow-md ring-1 ring-foreground/10 backdrop-blur",
        className,
      )}
    >
      <TimeSlider startTimeUtc={startTimeUtc} hour={sliderHour} onHourChange={setSliderHour} maxHour={maxHour} />
      <HeatmapLayerChoice
        layers={heatmapLayers}
        value={heatmapLayerKey}
        status={heatmapStatus}
        legendLevels={legendLevels}
        onChange={setHeatmapLayer}
      />
    </div>
  );
}
