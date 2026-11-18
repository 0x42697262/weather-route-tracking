import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { configDefaults, defineConfig } from "vitest/config";

const API_PATH_PREFIX = "/api";
const API_PROXY_TARGET_URL = "http://localhost:8000";
const SOURCE_DIR = fileURLToPath(new URL("./src", import.meta.url));
const TEST_SETUP_FILE = fileURLToPath(new URL("./src/test/setup.ts", import.meta.url));
const TEST_TIME_ZONE = "America/Chicago";
const E2E_GLOB = "e2e/**";
const REPOSITORY_ROOT_DIR = fileURLToPath(new URL("..", import.meta.url));

export default defineConfig({
  plugins: [react(), tailwindcss()],
  envDir: REPOSITORY_ROOT_DIR,
  resolve: {
    alias: {
      "@": SOURCE_DIR,
    },
  },
  server: {
    proxy: {
      [API_PATH_PREFIX]: {
        target: API_PROXY_TARGET_URL,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: [TEST_SETUP_FILE],
    exclude: [...configDefaults.exclude, E2E_GLOB],
    env: {
      TZ: TEST_TIME_ZONE,
    },
  },
});
