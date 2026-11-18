import { describe, expect, it } from "vitest";
import {
  DEFAULT_API_BASE_URL,
  DEFAULT_MAP_STYLE_URL,
  InvalidPublicConfigError,
  parsePublicConfig,
} from "@/config/parse";

describe("parsePublicConfig", () => {
  it("applies the defaults when nothing is set", () => {
    expect(parsePublicConfig({})).toEqual({
      apiBaseUrl: DEFAULT_API_BASE_URL,
      mapStyleUrl: DEFAULT_MAP_STYLE_URL,
    });
  });

  it("uses the values that are set", () => {
    const parsed = parsePublicConfig({
      VITE_API_BASE_URL: "https://app.example.com/api",
      VITE_MAP_STYLE_URL: "https://app.example.com/style.json",
    });
    expect(parsed).toEqual({
      apiBaseUrl: "https://app.example.com/api",
      mapStyleUrl: "https://app.example.com/style.json",
    });
  });

  it("returns a frozen object", () => {
    expect(Object.isFrozen(parsePublicConfig({}))).toBe(true);
  });

  it("rejects an invalid map style URL and names the variable", () => {
    expect(() => parsePublicConfig({ VITE_MAP_STYLE_URL: "not a url" })).toThrow(
      InvalidPublicConfigError,
    );
    expect(() => parsePublicConfig({ VITE_MAP_STYLE_URL: "not a url" })).toThrow(
      /VITE_MAP_STYLE_URL/,
    );
  });

  it("rejects an empty API base URL and names the variable", () => {
    expect(() => parsePublicConfig({ VITE_API_BASE_URL: "" })).toThrow(/VITE_API_BASE_URL/);
  });
});
