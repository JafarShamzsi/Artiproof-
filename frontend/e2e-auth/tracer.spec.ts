import { test, expect, guardAPIRequest } from "./fixtures";
import { randomUUID } from "node:crypto";

test("real signup tracer: UI registration, NextAuth login, backend session, revocation", async ({ page, request }) => {
  const email = `qa01-${randomUUID()}@example.com`;
  const password = "QA01-synthetic-passphrase-42";
  await page.goto("/register");
  await page.getByLabel(/Full Name/).fill("QA01 synthetic researcher");
  await page.getByLabel(/^Email/).fill(email);
  await page.getByLabel(/^Password/).fill(password);
  const registered = page.waitForResponse(response => response.url() === "http://127.0.0.1:8203/api/auth/register" && response.request().method() === "POST");
  await page.getByRole("button", { name: "Create Account", exact: true }).click();
  expect((await registered).status()).toBe(201);
  await expect(page).toHaveURL(/\/dashboard$/);
  const session = await (await guardAPIRequest(page.request).get("/api/auth/session")).json();
  expect(session.user.email).toBe(email);
  expect(session.accessToken).toEqual(expect.any(String));
  const headers = { Authorization: `Bearer ${session.accessToken}` };
  const me = await request.get("http://127.0.0.1:8203/api/auth/me", { headers });
  expect(me.status()).toBe(200);
  expect((await me.json()).email).toBe(email);
  expect((await request.get("http://127.0.0.1:8203/api/auth/me")).status()).toBe(401);
  expect((await request.post("http://127.0.0.1:8203/api/auth/logout", { headers })).status()).toBe(204);
  expect((await request.get("http://127.0.0.1:8203/api/auth/me", { headers })).status()).toBe(401);
});
