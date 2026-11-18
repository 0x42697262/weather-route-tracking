import { defineConfig } from "@playwright/test";

const DEFAULT_BASE_URL = "https://localhost";
const TEST_TIMEOUT_MS = 120_000;
const EXPECT_TIMEOUT_MS = 30_000;
const TIME_ZONE = "America/Chicago";

const chromiumPath = process.env.E2E_CHROMIUM_PATH;

export default defineConfig({
  testDir: "./e2e",
  timeout: TEST_TIMEOUT_MS,
  expect: { timeout: EXPECT_TIMEOUT_MS },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? DEFAULT_BASE_URL,
    ignoreHTTPSErrors: true,
    timezoneId: TIME_ZONE,
    viewport: { width: 390, height: 844 },
    launchOptions: {
      executablePath: chromiumPath === undefined || chromiumPath === "" ? undefined : chromiumPath,
      args: ["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
    },
  },
});
