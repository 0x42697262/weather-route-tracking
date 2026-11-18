import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@/index.css";
import { App } from "@/App";
import { configureMapWorker } from "@/features/map/maplibreWorker";
import { PreferencesProvider } from "@/features/preferences/PreferencesProvider";
import { ROOT_ELEMENT_ID } from "@/keys";
import { UiStoreProvider } from "@/state/UiStoreProvider";
import { bootText } from "@/text";
import { applyColorTokens } from "@/theme/colors";

const rootElement = document.getElementById(ROOT_ELEMENT_ID);
if (rootElement === null) {
  throw new Error(bootText.missingRootElement(ROOT_ELEMENT_ID));
}

configureMapWorker();
applyColorTokens(document.documentElement);

const queryClient = new QueryClient();

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <PreferencesProvider>
        <UiStoreProvider>
          <App />
        </UiStoreProvider>
      </PreferencesProvider>
    </QueryClientProvider>
  </StrictMode>,
);
