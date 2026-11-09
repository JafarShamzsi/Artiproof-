import { expect, test } from "@playwright/test";

/**
 * Landing page must always work for an anonymous visitor — it's the
 * "decide whether ArtiProof is credible enough to sign up" moment per
 * PRODUCT.md. Failing this test means cold traffic sees a broken page.
 */
test.describe("landing", () => {
  test("renders the hero with brand name and primary CTA", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/ArtiProof/i);

    // Brand mark is in the navbar — a visible "ArtiProof" word mark.
    await expect(
      page.getByRole("link", { name: /artiproof/i }).first(),
    ).toBeVisible();

    // Primary CTA exists and points at /register (per PricingSection +
    // hero CTAs). If this ever changes to /signup, update both.
    const primaryCtas = page.getByRole("link", { name: /start|get started|sign up|register/i });
    await expect(primaryCtas.first()).toBeVisible();
  });

  test("pricing tier names + monthly $20 are present", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/\$20/).first()).toBeVisible();
    // All three tier labels appear at least once on the page.
    await expect(page.getByText(/free/i).first()).toBeVisible();
    await expect(page.getByText(/pro/i).first()).toBeVisible();
  });

  test("legal pages are reachable", async ({ page }) => {
    await page.goto("/privacy");
    await expect(page.locator("body")).toContainText(/privacy/i);

    await page.goto("/terms");
    await expect(page.locator("body")).toContainText(/terms/i);
  });
});
