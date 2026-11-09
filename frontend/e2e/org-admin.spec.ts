import { expect, test } from "@playwright/test";

/**
 * Org-admin surface smoke. Same scope contract as the rest of the
 * smoke tier: we confirm routing + the public shape, not the
 * authenticated session-bearing path. Form-submission + role-change
 * flows live in the integration suite (which expects a seeded org +
 * a Bearer token).
 *
 * The org-management section is rendered conditionally for team-tier
 * users with an organization_id. Anonymous traffic never sees it; we
 * verify that the settings page (a) doesn't 500 on anon access (it
 * 3xxs to /login) and (b) the public Settings text strings that the
 * org-management section depends on don't accidentally leak into
 * other pages (the marketing copy).
 */
test.describe("org-admin section", () => {
  test("/settings does not 500 for anonymous traffic", async ({ page }) => {
    const response = await page.goto("/settings");
    expect(response?.status() ?? 200).toBeLessThan(500);
    // Either 3xx to login or 200 with chrome — both fine for smoke.
  });

  test("landing pages do not accidentally expose org-management copy", async ({
    page,
  }) => {
    // Quick regression guard: the org member-management copy ("Invite
    // by email") must not appear on the marketing pages. If a future
    // refactor accidentally exports the section to a landing route,
    // this catches it.
    for (const path of ["/", "/pricing", "/about", "/changelog"]) {
      await page.goto(path);
      await expect(
        page.getByText(/invite by email/i),
      ).toHaveCount(0);
    }
  });
});
