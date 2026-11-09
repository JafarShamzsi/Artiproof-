import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

/**
 * Vitest for the frontend unit/integration tests.
 *
 * Conventions:
 *   - jsdom environment so React component tests just work
 *   - vitest setup auto-loads @testing-library/jest-dom matchers
 *   - alias `@/...` matches tsconfig "paths" so component imports work
 *   - the `e2e/` folder is owned by Playwright; explicitly exclude it
 *     so vitest doesn't try to import the .spec files Playwright owns
 *   - `next/navigation`, `next-auth/react` are mocked in the setup file
 *     so any component that imports them works in jsdom without next env
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["node_modules/**", ".next/**", "e2e/**", "playwright-report/**"],
    css: false,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
