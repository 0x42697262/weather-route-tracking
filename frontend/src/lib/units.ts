import {
  CM_PER_INCH,
  DISPLAY_LOCALE,
  KG_PER_POUND,
  KM_PER_MILE,
  METRIC_FACTOR,
  MM_PER_INCH,
} from "@/constants";
import { unitText } from "@/text";

export const UNIT_SYSTEMS = ["imperial", "metric"] as const;

export type UnitSystem = (typeof UNIT_SYSTEMS)[number];

export const DEFAULT_UNIT_SYSTEM: UnitSystem = "imperial";

export const DIMENSIONS = ["distance", "speed", "rainRate", "snowRate", "mass"] as const;

export type Dimension = (typeof DIMENSIONS)[number];

export type DisplayUnit = Readonly<{
  metricPerDisplayUnit: number;
  label: string;
  fractionDigits: number;
}>;

export const DISPLAY_UNITS: Readonly<Record<UnitSystem, Readonly<Record<Dimension, DisplayUnit>>>> = {
  imperial: {
    distance: { metricPerDisplayUnit: KM_PER_MILE, label: unitText.mile, fractionDigits: 1 },
    speed: { metricPerDisplayUnit: KM_PER_MILE, label: unitText.milePerHour, fractionDigits: 0 },
    rainRate: { metricPerDisplayUnit: MM_PER_INCH, label: unitText.inchPerHour, fractionDigits: 2 },
    snowRate: { metricPerDisplayUnit: CM_PER_INCH, label: unitText.inchPerHour, fractionDigits: 1 },
    mass: { metricPerDisplayUnit: KG_PER_POUND, label: unitText.pound, fractionDigits: 0 },
  },
  metric: {
    distance: { metricPerDisplayUnit: METRIC_FACTOR, label: unitText.kilometer, fractionDigits: 1 },
    speed: {
      metricPerDisplayUnit: METRIC_FACTOR,
      label: unitText.kilometerPerHour,
      fractionDigits: 0,
    },
    rainRate: {
      metricPerDisplayUnit: METRIC_FACTOR,
      label: unitText.millimeterPerHour,
      fractionDigits: 1,
    },
    snowRate: {
      metricPerDisplayUnit: METRIC_FACTOR,
      label: unitText.centimeterPerHour,
      fractionDigits: 1,
    },
    mass: { metricPerDisplayUnit: METRIC_FACTOR, label: unitText.kilogram, fractionDigits: 0 },
  },
};

export function displayUnit(dimension: Dimension, system: UnitSystem): DisplayUnit {
  return DISPLAY_UNITS[system][dimension];
}

export function toDisplayValue(metricValue: number, dimension: Dimension, system: UnitSystem): number {
  return metricValue / displayUnit(dimension, system).metricPerDisplayUnit;
}

export function toMetricValue(displayValue: number, dimension: Dimension, system: UnitSystem): number {
  return displayValue * displayUnit(dimension, system).metricPerDisplayUnit;
}

export function formatDisplayNumber(displayValue: number, fractionDigits: number): string {
  return new Intl.NumberFormat(DISPLAY_LOCALE, {
    maximumFractionDigits: fractionDigits,
  }).format(displayValue);
}

export function formatMeasure(metricValue: number, dimension: Dimension, system: UnitSystem): string {
  const unit = displayUnit(dimension, system);
  const number = formatDisplayNumber(toDisplayValue(metricValue, dimension, system), unit.fractionDigits);
  return `${number} ${unit.label}`;
}

export const formatDistanceKm = (distanceKm: number, system: UnitSystem) =>
  formatMeasure(distanceKm, "distance", system);

export const formatSpeedKmh = (speedKmh: number, system: UnitSystem) =>
  formatMeasure(speedKmh, "speed", system);

export const formatRainRateMmPerH = (rainMmPerH: number, system: UnitSystem) =>
  formatMeasure(rainMmPerH, "rainRate", system);

export const formatSnowRateCmPerH = (snowCmPerH: number, system: UnitSystem) =>
  formatMeasure(snowCmPerH, "snowRate", system);

export const formatMassKg = (massKg: number, system: UnitSystem) =>
  formatMeasure(massKg, "mass", system);

export const DIMENSION_BY_METRIC_UNIT: Readonly<Partial<Record<string, Dimension>>> = {
  km: "distance",
  "km/h": "speed",
  "mm/h": "rainRate",
  "cm/h": "snowRate",
  kg: "mass",
};

export function formatMetricUnitValue(value: number, metricUnit: string, system: UnitSystem): string {
  const dimension = DIMENSION_BY_METRIC_UNIT[metricUnit];
  return dimension === undefined
    ? `${formatDisplayNumber(value, 1)} ${metricUnit}`
    : formatMeasure(value, dimension, system);
}
