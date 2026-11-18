import { z } from "zod";
import { PREFERENCES_SCHEMA_VERSION } from "@/constants";
import { DEFAULT_UNIT_SYSTEM, UNIT_SYSTEMS } from "@/lib/units";

export const MAP_STYLE_KEYS = ["configured"] as const;

export type MapStyleKey = (typeof MAP_STYLE_KEYS)[number];

export const DEFAULT_MAP_STYLE_KEY: MapStyleKey = "configured";

const preferencesSchema = z.object({
  schemaVersion: z.literal(PREFERENCES_SCHEMA_VERSION),
  units: z.enum(UNIT_SYSTEMS),
  mapStyle: z.enum(MAP_STYLE_KEYS),
});

export type Preferences = Readonly<z.infer<typeof preferencesSchema>>;

export const DEFAULT_PREFERENCES: Preferences = Object.freeze({
  schemaVersion: PREFERENCES_SCHEMA_VERSION,
  units: DEFAULT_UNIT_SYSTEM,
  mapStyle: DEFAULT_MAP_STYLE_KEY,
});

export function parseStoredPreferences(raw: string | null): Preferences {
  if (raw === null) {
    return DEFAULT_PREFERENCES;
  }
  try {
    const result = preferencesSchema.safeParse(JSON.parse(raw));
    return result.success ? Object.freeze(result.data) : DEFAULT_PREFERENCES;
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function serializePreferences(preferences: Preferences): string {
  return JSON.stringify(preferences);
}
