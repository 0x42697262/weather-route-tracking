import { useCallback, useSyncExternalStore } from "react";

const CHANGE_EVENT = "change";

export function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const mediaQuery = window.matchMedia(query);
      mediaQuery.addEventListener(CHANGE_EVENT, onChange);
      return () => mediaQuery.removeEventListener(CHANGE_EVENT, onChange);
    },
    [query],
  );
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(query).matches,
    () => false,
  );
}
