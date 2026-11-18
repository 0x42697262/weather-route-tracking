import { useState, type ReactNode } from "react";
import { UiStoreContext } from "@/state/context";
import { createUiStore, type UiStore } from "@/state/uiStore";

type UiStoreProviderProps = Readonly<{
  store?: UiStore;
  children: ReactNode;
}>;

export function UiStoreProvider({ store, children }: UiStoreProviderProps) {
  const [ownStore] = useState(() => store ?? createUiStore());
  return <UiStoreContext.Provider value={ownStore}>{children}</UiStoreContext.Provider>;
}
