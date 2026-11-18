export const LINE_STYLES = ["solid", "dashed", "hatched"] as const;

export type LineStyle = (typeof LINE_STYLES)[number];

export type ColorToken = Readonly<{
  hex: string;
  lineStyle: LineStyle;
}>;

export const COLOR_TOKENS = {
  "risk-low": { hex: "#4A7BB7", lineStyle: "solid" },
  "risk-moderate": { hex: "#FDB366", lineStyle: "solid" },
  "risk-high": { hex: "#F67E4B", lineStyle: "solid" },
  "risk-severe": { hex: "#DD3D2D", lineStyle: "solid" },
  "risk-no-travel": { hex: "#A50026", lineStyle: "solid" },
  "risk-unknown": { hex: "#8C8C8C", lineStyle: "hatched" },
  ferry: { hex: "#4B5563", lineStyle: "dashed" },
} as const satisfies Record<string, ColorToken>;

export type ColorKey = keyof typeof COLOR_TOKENS;

export const COLOR_KEYS = Object.keys(COLOR_TOKENS) as readonly ColorKey[];

export const UNKNOWN_COLOR_KEY: ColorKey = "risk-unknown";

export const FERRY_COLOR_KEY: ColorKey = "ferry";

export const MAP_COLORS = {
  selectedRouteCasing: "#FFFFFF",
  checkpointStroke: "#FFFFFF",
  truckFill: "#111827",
  truckStroke: "#FFFFFF",
  hatchStripe: "#FFFFFF",
} as const;

const CSS_VARIABLE_PREFIX = "--color-";

export function isColorKey(value: string): value is ColorKey {
  return Object.hasOwn(COLOR_TOKENS, value);
}

export function colorHex(key: ColorKey): string {
  return COLOR_TOKENS[key].hex;
}

export function cssVariableName(key: ColorKey): string {
  return `${CSS_VARIABLE_PREFIX}${key}`;
}

export function cssVariableReference(key: ColorKey): string {
  return `var(${cssVariableName(key)})`;
}

export function colorKeysWithLineStyle(lineStyle: LineStyle): readonly ColorKey[] {
  return COLOR_KEYS.filter((key) => COLOR_TOKENS[key].lineStyle === lineStyle);
}

export function applyColorTokens(element: HTMLElement): void {
  for (const key of COLOR_KEYS) {
    element.style.setProperty(cssVariableName(key), colorHex(key));
  }
}
