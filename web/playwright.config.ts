import { defineConfig, devices } from "@playwright/test";

import { E2E } from "./e2e/ports";

// `npm run test:e2e`: the real website against the real backend and a throwaway Postgres
// (e2e/stack.ts). Needs Docker Desktop open and the search model on disk. No AI review runs.
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/stack.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  // The first visit check builds the guideline search index, which can take minutes.
  timeout: 10 * 60 * 1000,
  expect: { timeout: 15 * 1000 },
  reporter: [["list"]],
  use: {
    baseURL: E2E.webOrigin,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], channel: "chrome", viewport: { width: 1366, height: 768 } } }],
  webServer: {
    command: `npx next dev --hostname 127.0.0.1 --port ${E2E.webPort}`,
    url: E2E.webOrigin,
    reuseExistingServer: false,
    timeout: 120 * 1000,
    env: {
      NEXT_PUBLIC_ARTEMIS_API_URL: E2E.apiUrl,
      // Its own build folder, so it can run beside the dev server.
      ARTEMIS_WEB_DIST_DIR: ".next-e2e",
    },
  },
});
