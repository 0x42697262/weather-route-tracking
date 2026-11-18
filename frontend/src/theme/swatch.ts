import type { CSSProperties } from "react";
import {
  DASH_LENGTH_PX,
  DASH_PERIOD_PX,
  HATCH_ANGLE_DEG,
  HATCH_PERIOD_PX,
  HATCH_STRIPE_PX,
} from "@/constants";
import {
  COLOR_TOKENS,
  MAP_COLORS,
  cssVariableReference,
  type ColorKey,
  type LineStyle,
} from "@/theme/colors";

const SWATCH_BACKGROUNDS: Readonly<Record<LineStyle, (color: string) => string>> = {
  solid: (color) => color,
  hatched: (color) =>
    `repeating-linear-gradient(${HATCH_ANGLE_DEG}deg, ${color} 0 ${HATCH_STRIPE_PX}px, ${MAP_COLORS.hatchStripe} ${HATCH_STRIPE_PX}px ${HATCH_PERIOD_PX}px)`,
  dashed: (color) =>
    `repeating-linear-gradient(to right, ${color} 0 ${DASH_LENGTH_PX}px, transparent ${DASH_LENGTH_PX}px ${DASH_PERIOD_PX}px)`,
};

export function swatchStyle(key: ColorKey): CSSProperties {
  const background = SWATCH_BACKGROUNDS[COLOR_TOKENS[key].lineStyle](cssVariableReference(key));
  return { background };
}
