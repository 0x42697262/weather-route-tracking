import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { optionsQuery } from "@/api/queries";
import { PreferencesProvider } from "@/features/preferences/PreferencesProvider";
import { createPreferencesStore } from "@/features/preferences/store";
import { UiStoreProvider } from "@/state/UiStoreProvider";
import { createUiStore, type UiStore } from "@/state/uiStore";
import { OPTIONS } from "@/test/fixtures";

export function renderWithApp(element: ReactElement, store: UiStore = createUiStore()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(optionsQuery.queryKey, OPTIONS);
  const result = render(
    <QueryClientProvider client={queryClient}>
      <PreferencesProvider store={createPreferencesStore(null)}>
        <UiStoreProvider store={store}>{element}</UiStoreProvider>
      </PreferencesProvider>
    </QueryClientProvider>,
  );
  return { ...result, queryClient, store };
}
