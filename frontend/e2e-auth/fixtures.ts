import { test as base, expect, type APIRequestContext, type Page } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { assertBrowserExecutionAllowed, guardAPIRequest } from "./network-policy";
export { guardAPIRequest } from "./network-policy";

export const backend = "http://127.0.0.1:8203";
export const password = "QA01-synthetic-passphrase-42";

export const test = base.extend<{ localOnly: void }>({
  request: async ({ request }, provide) => { await provide(guardAPIRequest(request)); },
  // No context/page dependency: do not resolve a browser before refusing execution.
  localOnly: [async ({}, use) => {
    assertBrowserExecutionAllowed();
    await use();
  }, { auto: true }],
});
export { expect };

export async function signup(page: Page, email: string) {
  await page.goto("/register");
  await page.getByLabel(/Full Name/).fill("QA01 synthetic researcher");
  await page.getByLabel(/^Email/).fill(email);
  await page.getByLabel(/^Password/).fill(password);
  const registered = page.waitForResponse(response => response.url() === `${backend}/api/auth/register` && response.request().method() === "POST");
  await page.getByRole("button", { name: "Create Account", exact: true }).click();
  expect((await registered).status()).toBe(201);
  await expect(page).toHaveURL(/\/dashboard$/);
  // New profiles auto-start onboarding asynchronously. Dismiss through real
  // UI before navigating, rather than racing the delayed modal or seeding UI state.
  await page.getByLabel("Skip tour", { exact: true }).click();
  return session(page);
}

export async function session(page: Page) {
  const response = await guardAPIRequest(page.request).get("/api/auth/session");
  expect(response.status()).toBe(200);
  const data = await response.json();
  expect(data.accessToken).toEqual(expect.any(String));
  return { data, headers: { Authorization: `Bearer ${data.accessToken}` } };
}

export async function mailLink(email: string, kind: "verify" | "invite") {
  const directory = process.env.QA_AUTH_ARTIFACTS;
  if (!directory) throw new Error("Missing test-owned mailbox directory");
  const filename = createHash("sha256").update(email.toLowerCase()).digest("hex") + ".json";
  let link: string | undefined;
  await expect.poll(async () => {
    try {
      const mail = JSON.parse(await readFile(path.join(directory, "mail", filename), "utf8"));
      const text: string = mail.text || mail.html;
      link = text.match(kind === "verify"
        ? /http:\/\/127\.0\.0\.1:3203\/verify-email\/[a-zA-Z0-9_-]+/
        : /http:\/\/127\.0\.0\.1:3203\/register\?invite=[a-zA-Z0-9_.-]+/)?.[0];
      return Boolean(link);
    } catch { return false; }
  }, { message: `Captured real ${kind} token in synthetic email sink` }).toBe(true);
  return link!;
}

export async function post(request: APIRequestContext, route: string, data: object, headers: Record<string, string>, status: number) {
  const response = await request.post(`${backend}${route}`, { data, headers });
  expect(response.status(), `${route}: ${await response.text()}`).toBe(status);
  return response;
}
