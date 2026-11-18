import { FERRY_COLOR_KEY, UNKNOWN_COLOR_KEY, isColorKey, type ColorKey } from "@/theme/colors";
import { LEVEL_ICONS } from "@/theme/icons";
import { swatchStyle } from "@/theme/swatch";
import { levelText } from "@/text";
import { cn } from "@/lib/utils";

export type LegendLevel = Readonly<{
  key: string;
  label: string;
  colorKey: string;
}>;

type LegendEntry = Readonly<{
  key: string;
  label: string;
  colorKey: ColorKey;
}>;

type LegendProps = Readonly<{
  levels: readonly LegendLevel[];
  className?: string;
}>;

const EXTRA_ENTRIES: readonly LegendEntry[] = [
  { key: UNKNOWN_COLOR_KEY, label: levelText.unknown, colorKey: UNKNOWN_COLOR_KEY },
  { key: FERRY_COLOR_KEY, label: levelText.ferry, colorKey: FERRY_COLOR_KEY },
];

function toEntry(level: LegendLevel): LegendEntry {
  return {
    key: level.key,
    label: level.label,
    colorKey: isColorKey(level.colorKey) ? level.colorKey : UNKNOWN_COLOR_KEY,
  };
}

export function Legend({ levels, className }: LegendProps) {
  const entries = [...levels.map(toEntry), ...EXTRA_ENTRIES];
  return (
    <ul aria-label={levelText.legendTitle} className={cn("flex flex-col gap-1.5 text-sm", className)}>
      {entries.map((entry) => {
        const Icon = LEVEL_ICONS[entry.colorKey];
        return (
          <li key={entry.key} className="flex items-center gap-2" data-color-key={entry.colorKey}>
            <span
              aria-hidden="true"
              className="h-2.5 w-6 shrink-0 rounded-full ring-1 ring-foreground/10"
              style={swatchStyle(entry.colorKey)}
            />
            <Icon aria-hidden="true" className="size-4 shrink-0" />
            <span>{entry.label}</span>
          </li>
        );
      })}
    </ul>
  );
}
