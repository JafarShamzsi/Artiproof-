import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { assertBrowserExecutionAllowed } from "./e2e-auth/network-policy";

// Refuse direct Playwright invocation (including collection) before configuration
// can launch a browser. Lifting this needs a separately reviewed design/change.
assertBrowserExecutionAllowed();

// Deliberately separate from the unchanged default smoke suite.
const artifacts = process.env.QA_AUTH_ARTIFACTS ?? (() => {
  throw new Error("Run through scripts/qa_auth/run.py (owned disposable services required)");
})();
const slice = process.env.QA_AUTH_BROWSER_SLICE || "browser";

export default defineConfig({
  testDir: "./e2e-auth",
  testMatch: "**/*.spec.ts", // Node-only policy checks must not become browser tests.
  outputDir: path.join(artifacts, "playwright", slice),
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  reporter: [["list"], ["json", { outputFile: path.join(artifacts, `${slice}.json`) }]],
  use: {
    baseURL: "http://127.0.0.1:3203",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    serviceWorkers: "block",
  },
  projects: [{ name: "authenticated-chromium", use: { ...devices["Desktop Chrome"] } }],
  // No webServer reuse: the test-owned runner starts and stops only its processes.
});
