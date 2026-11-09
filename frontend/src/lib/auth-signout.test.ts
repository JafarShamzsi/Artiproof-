import { afterEach, expect, it, vi } from "vitest";
import { createRequire } from "node:module";
import path from "node:path";
import { authOptions } from "./auth";

const require = createRequire(import.meta.url);
// The installed handler is deliberately exercised, not just our event function.
const signout = require(path.resolve("node_modules/next-auth/core/routes/signout.js")).default;
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

async function logout(accessToken: string | undefined = "synthetic-platform-bearer") {
  const clean = vi.fn(() => [{ name: "synthetic-session", value: "", options: { maxAge: 0 } }]);
  const logger = { error: vi.fn() };
  const result = await signout({ options: { ...authOptions, events: authOptions.events ?? {},
    jwt: { decode: async () => ({ id: "synthetic-user", accessToken }) }, callbackUrl: "/", logger },
    sessionStore: { value: "synthetic-cookie", clean } });
  expect(clean).toHaveBeenCalledOnce();
  expect(result.cookies[0].options.maxAge).toBe(0);
  expect(result.redirect).toBe("/");
  expect(logger.error).not.toHaveBeenCalled();
}

it("ordinary installed NextAuth JWT signout revokes the server-held platform bearer", async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, status: 204 });
  vi.stubGlobal("fetch", fetch);
  await logout();
  expect(fetch).toHaveBeenCalledOnce();
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/auth/logout"), expect.objectContaining({
    method: "POST", headers: { Authorization: "Bearer synthetic-platform-bearer" }, cache: "no-store",
    signal: expect.any(AbortSignal),
  }));
});

it.each(["network", "http", "unexpected-200"])("revocation failure (%s) cannot prevent local cookie logout or leak payloads", async (failure) => {
  const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
  const fetch = vi.fn().mockImplementation(async () => {
    if (failure === "http") return { ok: false, status: 503 };
    if (failure === "unexpected-200") return { ok: true, status: 200 };
    throw new Error("SYNTHETIC_PRIVATE_BEARER_OR_URL");
  });
  vi.stubGlobal("fetch", fetch);
  await logout();
  expect(fetch).toHaveBeenCalledOnce();
  expect(warn).toHaveBeenCalledWith("Backend session revocation failed; local sign-out continues.");
  expect(JSON.stringify(warn.mock.calls)).not.toContain("SYNTHETIC_PRIVATE");
});

it("bounds the server revocation attempt to five seconds and still clears local cookies", async () => {
  vi.useFakeTimers();
  const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.spyOn(AbortSignal, "timeout").mockImplementation((milliseconds) => {
    expect(milliseconds).toBe(5000);
    const controller = new AbortController();
    setTimeout(() => controller.abort(), milliseconds);
    return controller.signal;
  });
  vi.stubGlobal("fetch", vi.fn().mockImplementation((_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener("abort", () => reject(new Error("synthetic-abort")));
  })));
  const pending = logout();
  await vi.advanceTimersByTimeAsync(5000);
  await pending;
  expect(warn).toHaveBeenCalledWith("Backend session revocation failed; local sign-out continues.");
});

it("missing backend bearer does not trigger a request", async () => {
  const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  await logout("");
  expect(fetch).not.toHaveBeenCalled();
});
