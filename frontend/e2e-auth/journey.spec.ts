import { randomUUID } from "node:crypto";
import { test, expect, backend, password, signup, session, mailLink, post } from "./fixtures";

test("real verified invitation consent, removal, analysis/report access and revoked browser session", async ({ page, request }) => {
  const email = `qa01-member-${randomUUID()}@example.com`;
  const ownerEmail = `qa01-owner-${randomUUID()}@example.com`;
  const member = await signup(page, email);
  const owner = await (await post(request, "/api/auth/register", {
    email: ownerEmail, password, full_name: "QA01 synthetic owner",
  }, {}, 201)).json();
  const ownerHeaders = { Authorization: `Bearer ${owner.access_token}` };
  const org = await (await post(request, "/api/organizations", { name: `QA01 ${randomUUID()}` }, ownerHeaders, 201)).json();
  await post(request, `/api/organizations/${org.id}/members/invite`, { email, role: "member" }, ownerHeaders, 201);
  const invitation = await mailLink(email, "invite");
  const token = new URL(invitation).searchParams.get("invite")!;

  // Neither opening/previewing an invite nor registration silently enrolls.
  expect((await (await request.get(`${backend}/api/auth/me`, { headers: member.headers })).json()).organization_id).toBeNull();
  await post(request, `/api/organizations/${org.id}/invites/accept`, { token }, member.headers, 403);
  // Initial verification email was overwritten by the invite in the mailbox;
  // request a real fresh link through the production verification route.
  await post(request, "/api/auth/me/email/verify/request", {}, member.headers, 200);
  await page.goto(await mailLink(email, "verify"));
  await expect(page.getByText("Email verified", { exact: true })).toBeVisible();
  expect((await (await request.get(`${backend}/api/auth/me/email/status`, { headers: member.headers })).json()).verified).toBe(true);
  await page.goto(invitation);
  await page.getByRole("button", { name: "Review invitation", exact: true }).click();
  await expect(page.getByRole("button", { name: "Accept invitation and join team", exact: true })).toBeVisible();
  expect((await (await request.get(`${backend}/api/auth/me`, { headers: member.headers })).json()).organization_id).toBeNull();
  await page.getByRole("button", { name: "Accept invitation and join team", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Invitation accepted." })).toBeVisible();
  const refreshed = await session(page);
  expect(refreshed.data.user.organizationId).toBe(org.id);
  expect(refreshed.data.user.tier).toBe("free");

  // Real UI submission and persisted pending state, NOT broker publication.
  await page.goto("/check");
  await page.getByRole("tab", { name: "Paste Text", exact: true }).click();
  await page.getByPlaceholder("Paste the article text here...").fill("QA01 synthetic source text for authorization testing. No real paper, customer data, or external URL is used. This submission tests persisted pending state only, not broker publication or model quality.");
  const submitted = page.waitForResponse(response => response.url() === `${backend}/api/source-check/` && response.request().method() === "POST");
  await page.getByRole("button", { name: "Analyze", exact: true }).click();
  const response = await submitted;
  expect(response.status()).toBe(201);
  const source = await response.json();
  expect(source.status).toBe("pending");
  await page.goto(`/check/${source.id}`);
  expect((await request.get(`${backend}/api/source-check/${source.id}`, { headers: refreshed.headers })).status()).toBe(200);
  const report = await (await post(request, "/api/reports/generate", { source_check_id: source.id }, refreshed.headers, 201)).json();
  // A report of a queued/unassessed source is not a completed analysis.
  await page.goto("/reports");
  await expect(page.getByText(report.title, { exact: true })).toBeVisible();
  const pdf = await request.get(`${backend}/api/reports/${report.id}/download`, { headers: refreshed.headers });
  expect(pdf.status()).toBe(200);
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
  expect((await request.get(`${backend}/api/reports/${report.id}`)).status()).toBe(401);
  expect((await request.delete(`${backend}/api/organizations/${org.id}/members/${member.data.user.id}`, { headers: ownerHeaders })).status()).toBe(204);
  expect((await request.get(`${backend}/api/organizations/${org.id}/members`, { headers: refreshed.headers })).status()).toBe(403);
  expect((await (await request.get(`${backend}/api/auth/me`, { headers: refreshed.headers })).json()).organization_id).toBeNull();
  expect((await request.post(`${backend}/api/auth/logout`, { headers: refreshed.headers })).status()).toBe(204);
  for (const route of [`/api/source-check/${source.id}`, `/api/reports/${report.id}`, `/api/reports/${report.id}/download`]) {
    expect((await request.get(`${backend}${route}`, { headers: refreshed.headers })).status()).toBe(401);
  }
  // Existing NextAuth cookie must not restore backend authorization after revocation.
  await page.goto("/check");
  await expect(page).toHaveURL(/\/login(?:\?|$)/);
});
