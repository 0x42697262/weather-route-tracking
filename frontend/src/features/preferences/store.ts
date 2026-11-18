import {
  parseStoredPreferences,
  serializePreferences,
  type Preferences,
} from "@/features/preferences/preferences";
import { PREFERENCES_STORAGE_KEY } from "@/keys";

export type PreferencesStorage = Pick<Storage, "getItem" | "setItem">;

export type PreferencesUpdate = Partial<Omit<Preferences, "schemaVersion">>;

export type PreferencesStore = Readonly<{
  getSnapshot: () => Preferences;
  subscribe: (listener: () => void) => () => void;
  update: (change: PreferencesUpdate) => void;
}>;

function readStored(storage: PreferencesStorage | null): string | null {
  try {
    return storage?.getItem(PREFERENCES_STORAGE_KEY) ?? null;
  } catch {
    return null;
  }
}

function writeStored(storage: PreferencesStorage | null, value: string): void {
  try {
    storage?.setItem(PREFERENCES_STORAGE_KEY, value);
  } catch {
    return;
  }
}

export function createPreferencesStore(storage: PreferencesStorage | null): PreferencesStore {
  let current = parseStoredPreferences(readStored(storage));
  const listeners = new Set<() => void>();

  return Object.freeze({
    getSnapshot: () => current,
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    update: (change: PreferencesUpdate) => {
      current = Object.freeze({ ...current, ...change });
      writeStored(storage, serializePreferences(current));
      for (const listener of listeners) {
        listener();
      }
    },
  });
}

export function browserPreferencesStorage(): PreferencesStorage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}
