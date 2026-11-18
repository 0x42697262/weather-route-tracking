import { useState, type ReactNode } from "react";
import { PreferencesContext } from "@/features/preferences/context";
import {
  browserPreferencesStorage,
  createPreferencesStore,
  type PreferencesStore,
} from "@/features/preferences/store";

type PreferencesProviderProps = Readonly<{
  store?: PreferencesStore;
  children: ReactNode;
}>;

export function PreferencesProvider({ store, children }: PreferencesProviderProps) {
  const [ownStore] = useState(() => store ?? createPreferencesStore(browserPreferencesStorage()));
  return <PreferencesContext.Provider value={ownStore}>{children}</PreferencesContext.Provider>;
}
