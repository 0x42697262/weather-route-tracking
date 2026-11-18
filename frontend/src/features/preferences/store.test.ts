import { describe, expect, it, vi } from "vitest";
import { DEFAULT_PREFERENCES, parseStoredPreferences } from "@/features/preferences/preferences";
import { createPreferencesStore, type PreferencesStorage } from "@/features/preferences/store";
import { PREFERENCES_STORAGE_KEY } from "@/keys";

function memoryStorage(initial: Record<string, string> = {}): PreferencesStorage & {
  values: Map<string, string>;
} {
  const values = new Map(Object.entries(initial));
  return {
    values,
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => {
      values.set(key, value);
    },
  };
}

describe("parseStoredPreferences", () => {
  it("defaults to imperial units and the configured map style", () => {
    expect(parseStoredPreferences(null)).toEqual({
      schemaVersion: 1,
      units: "imperial",
      mapStyle: "configured",
    });
  });

  it("reads a valid stored value", () => {
    const stored = JSON.stringify({ schemaVersion: 1, units: "metric", mapStyle: "configured" });
    expect(parseStoredPreferences(stored).units).toBe("metric");
  });

  it.each([
    ["malformed JSON", "{not json"],
    ["an unknown schema version", JSON.stringify({ schemaVersion: 99, units: "metric", mapStyle: "configured" })],
    ["an unknown unit system", JSON.stringify({ schemaVersion: 1, units: "furlongs", mapStyle: "configured" })],
    ["a missing field", JSON.stringify({ schemaVersion: 1, units: "metric" })],
    ["a non-object", JSON.stringify("metric")],
  ])("discards %s and falls back to defaults", (_, stored) => {
    expect(parseStoredPreferences(stored)).toEqual(DEFAULT_PREFERENCES);
  });
});

describe("createPreferencesStore", () => {
  it("starts from what is stored", () => {
    const storage = memoryStorage({
      [PREFERENCES_STORAGE_KEY]: JSON.stringify({
        schemaVersion: 1,
        units: "metric",
        mapStyle: "configured",
      }),
    });
    expect(createPreferencesStore(storage).getSnapshot().units).toBe("metric");
  });

  it("writes a versioned value and notifies subscribers on update", () => {
    const storage = memoryStorage();
    const store = createPreferencesStore(storage);
    const listener = vi.fn();
    const unsubscribe = store.subscribe(listener);

    store.update({ units: "metric" });

    expect(listener).toHaveBeenCalledTimes(1);
    expect(store.getSnapshot().units).toBe("metric");
    expect(JSON.parse(storage.values.get(PREFERENCES_STORAGE_KEY) ?? "")).toEqual({
      schemaVersion: 1,
      units: "metric",
      mapStyle: "configured",
    });

    unsubscribe();
    store.update({ units: "imperial" });
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("keeps working in memory when storage throws", () => {
    const failing: PreferencesStorage = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    const store = createPreferencesStore(failing);
    expect(store.getSnapshot()).toEqual(DEFAULT_PREFERENCES);
    store.update({ units: "metric" });
    expect(store.getSnapshot().units).toBe("metric");
  });

  it("works without storage", () => {
    const store = createPreferencesStore(null);
    store.update({ units: "metric" });
    expect(store.getSnapshot().units).toBe("metric");
  });
});
