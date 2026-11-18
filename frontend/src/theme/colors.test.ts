import { describe, expect, it } from "vitest";
import {
  COLOR_KEYS,
  applyColorTokens,
  colorHex,
  colorKeysWithLineStyle,
  cssVariableName,
  isColorKey,
} from "@/theme/colors";
import { LEVEL_ICONS } from "@/theme/icons";

describe("color tokens", () => {
  it("covers every server color key plus unknown and ferry", () => {
    expect(COLOR_KEYS).toEqual([
      "risk-low",
      "risk-moderate",
      "risk-high",
      "risk-severe",
      "risk-no-travel",
      "risk-unknown",
      "ferry",
    ]);
  });

  it("gives every key a distinct hex color and an icon", () => {
    const hexes = COLOR_KEYS.map(colorHex);
    expect(new Set(hexes).size).toBe(hexes.length);
    for (const key of COLOR_KEYS) {
      expect(colorHex(key)).toMatch(/^#[0-9A-F]{6}$/);
      expect(LEVEL_ICONS[key]).toBeDefined();
    }
  });

  it("splits keys by line style", () => {
    expect(colorKeysWithLineStyle("hatched")).toEqual(["risk-unknown"]);
    expect(colorKeysWithLineStyle("dashed")).toEqual(["ferry"]);
  });

  it("recognizes only known keys", () => {
    expect(isColorKey("risk-high")).toBe(true);
    expect(isColorKey("risk-purple")).toBe(false);
  });

  it("writes one CSS variable per key", () => {
    const element = document.createElement("div");
    applyColorTokens(element);
    expect(element.style.getPropertyValue(cssVariableName("risk-low"))).toBe(colorHex("risk-low"));
  });
});
