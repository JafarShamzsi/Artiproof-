import { randomUUID } from "node:crypto";
import { test, expect, backend, signup, post } from "./fixtures";

test("real personal UI submission and unassessed PDF access, revoked browser cookie denied", async ({ page, request }) => {
  const user = await signup(page, `qa01-resource-${randomUUID()}@example.com`);
  await page.goto("/check");
  await page.getByRole("tab", { name: "Paste Text", exact: true }).click();
  await page.getByPlaceholder("Paste the article text here...").fill("QA01 synthetic source text for authorization testing. No customer paper or external URL. This submission tests persisted pending state only, not broker publication, model quality or completed worker execution.");
  const submitted = page.waitForResponse(response => response.url() === `${backend}/api/source-check/` && response.request().method() === "POST");
  await page.getByRole("button", { name: "Analyze", exact: true }).click();
  const response = await submitted;
  expect(response.status()).toBe(201);
  const source = await response.json();
  expect(source.status).toBe("pending");
  await page.goto(`/check/${source.id}`);
  expect((await request.get(`${backend}/api/source-check/${source.id}`, { headers: user.headers })).status()).toBe(200);
  const report = await (await post(request, "/api/reports/generate", { source_check_id: source.id }, user.headers, 201)).json();
  await page.goto("/reports");
  await expect(page.getByText(report.title, { exact: true })).toBeVisible();
  const pdf = await request.get(`${backend}/api/reports/${report.id}/download`, { headers: user.headers });
  expect(pdf.status()).toBe(200);
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
  expect(pdf.headers()["x-report-renderer"]).toMatch(/^(cached|weasyprint|pymupdf-fallback)$/);
  expect((await request.get(`${backend}/api/reports/${report.id}`)).status()).toBe(401);
  expect((await request.post(`${backend}/api/auth/logout`, { headers: user.headers })).status()).toBe(204);
  for (const route of [`/api/source-check/${source.id}`, `/api/reports/${report.id}`, `/api/reports/${report.id}/download`]) {
    expect((await request.get(`${backend}${route}`, { headers: user.headers })).status()).toBe(401);
  }
  await page.goto("/check");
  await expect(page).toHaveURL(/\/login(?:\?|$)/);
});
