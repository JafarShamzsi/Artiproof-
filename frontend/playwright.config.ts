import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright smoke tests for ArtiProof.
 *
 * Scope: paths that do NOT require a running backend or external API keys
 * (Gemini, CrossRef, Resend). CI uses the preceding production build;
 * local runs default to a dev server if PLAYWRIGHT_NO_WEBSERVER is unset.
 *
 * Larger end-to-end flows (signup → first analysis, scheduled-report
 * delivery, researcher analysis) need a real backend + Celery + DB
 * seeding and live in a separate `e2e/` suite tracked in the integration
 * roadmap. The smoke suite below catches the regressions that break
 * everything (broken auth gate, missing CTAs, schema-incompatible
 * landing) which is what `npm run test:smoke` should always run.
 */
export default defineConfig({
  testDir: "./e2e",
  // Keep Playwright cleanup separate from unit/audit/build evidence.
  outputDir: "./test-results/playwright",
  timeout: 30 * 1000,
  expect: { timeout: 5000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI
    ? [["github"], ["html", { open: "never" }], ["junit", { outputFile: "test-results/smoke.xml" }]]
    : "list",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: process.env.PLAYWRIGHT_NO_WEBSERVER
    ? undefined
    : {
        command: process.env.CI ? "npm run start" : "npm run dev",
        url: "http://localhost:3000",
        reuseExistingServer: !process.env.CI,
        timeout: 120 * 1000,
      },
});
