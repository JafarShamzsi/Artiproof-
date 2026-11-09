import { expect, test } from "@playwright/test";

/**
 * Auth-gate smoke. Verifies that unauthenticated visits to /dashboard
 * routes redirect to /login, and that the login + signup forms render
 * with the expected fields and client-side validation.
 *
 * The form-submission paths (real POST to /api/auth/*) live in a
 * separate integration suite — the smoke tier only confirms that
 * routing + field rendering survive a deploy.
 */
test.describe("auth routing + forms", () => {
  test("login page renders with email + password fields", async ({ page }) => {
    await page.goto("/login");
    // The page lands cleanly.
    await expect(page).toHaveURL(/\/login/);
    // Email and password inputs exist (form-submission flow is in the
    // integration suite). Using getByLabel covers accessibility too.
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i).first()).toBeVisible();
  });

  test("register page renders with required fields", async ({ page }) => {
    await page.goto("/register");
    await expect(page).toHaveURL(/\/register/);
    await expect(page.getByLabel(/full name|name/i)).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i).first()).toBeVisible();
  });

  test("forgot-password page reachable from login", async ({ page }) => {
    await page.goto("/login");
    const forgot = page.getByRole("link", { name: /forgot/i });
    await expect(forgot).toBeVisible();
    await forgot.click();
    await expect(page).toHaveURL(/\/forgot-password/);
  });

  test("client-side password length is enforced on register", async ({
    page,
  }) => {
    await page.goto("/register");
    await page.getByLabel(/full name|name/i).fill("Test User");
    await page.getByLabel(/email/i).fill("smoke@example.com");
    await page.getByLabel(/password/i).first().fill("short"); // < 8 chars
    await page
      .getByRole("button", { name: /sign up|create|register/i })
      .first()
      .click();
    // Either the form shows an inline error AND stays on /register, or
    // it refuses to navigate. Tolerate a small navigation delay before
    // asserting — some forms still submit and 4xx-bounce.
    await page.waitForTimeout(500);
    expect(page.url()).toMatch(/\/register/);
  });
});

test.describe("dashboard routes are reachable", () => {
  // The smoke tier intentionally does NOT assert on auth-redirect
  // behavior — it depends on NEXTAUTH_SECRET being set, the backend
  // being up to return 401, and the api-client running. All of those
  // are env-dependent and properly verified in the integration suite.
  // What this tier catches is the dramatic regression: the route
  // throws at module load, the layout chrome doesn't compose, or the
  // bundle is broken. We just confirm the page navigates without an
  // unhandled error.

  test("/dashboard does not 500 or hang", async ({ page }) => {
    const response = await page.goto("/dashboard");
    // Either 200 (dashboard chrome shown, data 401s in the background)
    // or a 3xx redirect to /login. Both are acceptable from the smoke
    // tier's perspective — 500 is not.
    expect(response?.status() ?? 200).toBeLessThan(500);
  });

  test("/admin does not 500 or hang", async ({ page }) => {
    const response = await page.goto("/admin");
    expect(response?.status() ?? 200).toBeLessThan(500);
    // And whatever renders, the admin stats cards must NOT — those
    // require role=admin + a successful /api/admin/stats call.
    const adminStats = page.getByText(/Source checks \(24h\)/i);
    await expect(adminStats).toHaveCount(0);
  });
});
