import { useState } from "react";
import { Slider } from "@/components/ui/slider";
import { DEFAULT_FORECAST_HOURS, SLIDER_STEP_HOURS } from "@/constants";
import { useAnimationFrameCallback } from "@/hooks/useAnimationFrameCallback";
import { formatHourFromStart } from "@/lib/format";
import { sliderText } from "@/text";

type TimeSliderProps = Readonly<{
  startTimeUtc: string | null;
  hour: number;
  onHourChange: (hour: number) => void;
  maxHour?: number;
}>;

function firstValue(value: number | readonly number[]): number {
  return typeof value === "number" ? value : (value[0] ?? 0);
}

export function TimeSlider({
  startTimeUtc,
  hour,
  onHourChange,
  maxHour = DEFAULT_FORECAST_HOURS,
}: TimeSliderProps) {
  const [displayHour, setDisplayHour] = useState(hour);
  const [lastHour, setLastHour] = useState(hour);
  if (hour !== lastHour) {
    setLastHour(hour);
    setDisplayHour(hour);
  }
  const emitHour = useAnimationFrameCallback(onHourChange);
  const disabled = startTimeUtc === null;
  const label = startTimeUtc === null ? sliderText.unavailableHint : formatHourFromStart(startTimeUtc, displayHour);

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="truncate font-medium" aria-live="off">
          {label}
        </span>
        {disabled ? null : (
          <span className="shrink-0 text-muted-foreground tabular-nums">
            {sliderText.hourOffset(displayHour)}
          </span>
        )}
      </div>
      <Slider
        min={0}
        max={maxHour}
        step={SLIDER_STEP_HOURS}
        value={[displayHour]}
        disabled={disabled}
        onValueChange={(value) => {
          const next = firstValue(value);
          setDisplayHour(next);
          emitHour(next);
        }}
        thumbProps={{ "aria-label": sliderText.label, getAriaValueText: () => label }}
        className="py-3"
        thumbClassName="size-6 after:-inset-2.5"
      />
    </div>
  );
}
