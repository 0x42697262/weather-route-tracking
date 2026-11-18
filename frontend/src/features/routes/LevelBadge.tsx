import type { LevelLook } from "@/features/levels/levelTable";
import { cn } from "@/lib/utils";
import { LEVEL_ICONS } from "@/theme/icons";
import { swatchStyle } from "@/theme/swatch";

type LevelBadgeProps = Readonly<{
  look: LevelLook;
  className?: string;
}>;

export function LevelBadge({ look, className }: LevelBadgeProps) {
  const Icon = LEVEL_ICONS[look.colorKey];
  return (
    <span
      data-color-key={look.colorKey}
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full border bg-background py-0.5 pr-2 pl-1 text-xs font-medium",
        className,
      )}
    >
      <span aria-hidden="true" className="size-3 rounded-full" style={swatchStyle(look.colorKey)} />
      <Icon aria-hidden="true" className="size-3.5" />
      {look.label}
    </span>
  );
}
