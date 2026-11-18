import { describe, expect, it } from "vitest";
import {
  DIMENSIONS,
  UNIT_SYSTEMS,
  formatDistanceKm,
  formatMassKg,
  formatRainRateMmPerH,
  formatSnowRateCmPerH,
  formatSpeedKmh,
  toDisplayValue,
  toMetricValue,
} from "@/lib/units";

describe("toDisplayValue", () => {
  it.each([
    ["distance", 1.609344, 1],
    ["speed", 88.51392, 55],
    ["rainRate", 25.4, 1],
    ["snowRate", 2.54, 1],
    ["mass", 0.45359237, 1],
  ] as const)("converts %s exactly to imperial", (dimension, metricValue, expected) => {
    expect(toDisplayValue(metricValue, dimension, "imperial")).toBeCloseTo(expected, 10);
  });

  it.each(DIMENSIONS)("leaves %s unchanged for metric", (dimension) => {
    expect(toDisplayValue(42.5, dimension, "metric")).toBe(42.5);
  });
});

describe("toMetricValue", () => {
  it.each(UNIT_SYSTEMS.flatMap((system) => DIMENSIONS.map((dimension) => [system, dimension] as const)))(
    "round-trips %s %s",
    (system, dimension) => {
      expect(toDisplayValue(toMetricValue(30_000, dimension, system), dimension, system)).toBeCloseTo(
        30_000,
        6,
      );
    },
  );

  it("converts a load in pounds to kilograms", () => {
    expect(toMetricValue(40_000, "mass", "imperial")).toBeCloseTo(18_143.6948, 4);
  });
});

describe("formatters", () => {
  it("formats imperial values with their labels", () => {
    expect(formatDistanceKm(160.9344, "imperial")).toBe("100 mi");
    expect(formatSpeedKmh(56.327, "imperial")).toBe("35 mph");
    expect(formatRainRateMmPerH(6.35, "imperial")).toBe("0.25 in/h");
    expect(formatSnowRateCmPerH(1.27, "imperial")).toBe("0.5 in/h");
    expect(formatMassKg(14_514.96, "imperial")).toBe("32,000 lb");
  });

  it("formats metric values with their labels", () => {
    expect(formatDistanceKm(12.345, "metric")).toBe("12.3 km");
    expect(formatSpeedKmh(88.6, "metric")).toBe("89 km/h");
    expect(formatRainRateMmPerH(2.54, "metric")).toBe("2.5 mm/h");
    expect(formatSnowRateCmPerH(1.27, "metric")).toBe("1.3 cm/h");
    expect(formatMassKg(18_000, "metric")).toBe("18,000 kg");
  });
});
