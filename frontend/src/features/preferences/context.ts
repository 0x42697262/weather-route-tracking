import { createContext, useContext, useSyncExternalStore } from "react";
import type { Preferences } from "@/features/preferences/preferences";
import { bootText } from "@/text";
import type { PreferencesStore, PreferencesUpdate } from "@/features/preferences/store";

export const PreferencesContext = createContext<PreferencesStore | null>(null);

const PROVIDER_NAME = "PreferencesProvider";

function usePreferencesStore(): PreferencesStore {
  const store = useContext(PreferencesContext);
  if (store === null) {
    throw new Error(bootText.missingProvider(PROVIDER_NAME));
  }
  return store;
}

export function usePreferences(): Preferences {
  const store = usePreferencesStore();
  return useSyncExternalStore(store.subscribe, store.getSnapshot);
}

export function useUpdatePreferences(): (change: PreferencesUpdate) => void {
  return usePreferencesStore().update;
}
