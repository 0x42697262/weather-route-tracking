import { createContext, useContext, useSyncExternalStore } from "react";
import type { UiActions, UiState, UiStore } from "@/state/uiStore";
import { bootText } from "@/text";

export const UiStoreContext = createContext<UiStore | null>(null);

const PROVIDER_NAME = "UiStoreProvider";

function useUiStore(): UiStore {
  const store = useContext(UiStoreContext);
  if (store === null) {
    throw new Error(bootText.missingProvider(PROVIDER_NAME));
  }
  return store;
}

export function useUiState<Selected>(selector: (state: UiState) => Selected): Selected {
  const store = useUiStore();
  return useSyncExternalStore(store.subscribe, () => selector(store.getSnapshot()));
}

export function useUiActions(): UiActions {
  return useUiStore().actions;
}
