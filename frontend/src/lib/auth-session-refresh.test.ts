import { afterEach, expect, it, vi } from "vitest";
import { authOptions } from "./auth";
import type { Session } from "next-auth";

const jwt = authOptions.callbacks!.jwt!;
const sessionCallback = authOptions.callbacks!.session!;
const prior = () => ({ id: "recipient", role: "researcher", tier: "free", organizationId: null, accessToken: "existing-access-token" });
const account = { id: "recipient", email: "recipient@example.com", full_name: "Recipient", institution: null,
  role: "researcher", tier: "team", organization_id: "actual-org", org_role: "member" };
type JwtArgs = Parameters<typeof jwt>[0];
afterEach(() => vi.unstubAllGlobals());

it("refreshes the same authenticated session from the backend, ignoring client authorization fields", async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => account });
  vi.stubGlobal("fetch", fetch);
  const old = prior();
  const refreshed = await jwt({ token: old, trigger: "update", session: {
    tier: "team", organizationId: "attacker-org", role: "admin", accessToken: "attacker-token",
  } } as JwtArgs);
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/auth/me"), expect.objectContaining({
    headers: { Authorization: "Bearer existing-access-token" }, cache: "no-store",
  }));
  expect(refreshed).toMatchObject({ organizationId: "actual-org", role: "researcher", tier: "team", accessToken: "existing-access-token" });
  expect(old).toEqual(prior());
  const session = await sessionCallback({ session: { user: { id: "recipient" }, expires: "2099-01-01" }, token: refreshed } as Parameters<typeof sessionCallback>[0]) as Session;
  expect(session.user.organizationId).toBe("actual-org");
  expect(session.accessToken).toBe("existing-access-token");
});

it.each(["http", "network", "wrong-user", "pointer-only", "malformed"])("refresh failure (%s) leaves the old token unchanged", async (failure) => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => {
    if (failure === "network") throw new Error("offline");
    return { ok: failure !== "http", status: 503, json: async () => failure === "wrong-user" ? { ...account, id: "other" }
      : failure === "pointer-only" ? { ...account, org_role: null }
      : failure === "malformed" ? { id: "recipient" } : account };
  }));
  const token = prior();
  // NextAuth v4 cleans the session cookie if the jwt callback throws. Keep
  // authorization unchanged and surface a typed error instead of logging out.
  const failed = await jwt({ token, trigger: "update", session: { organizationId: "forged", role: "admin" } } as JwtArgs);
  expect(failed).toMatchObject({ ...prior(), accountRefreshError: "ACCOUNT_REFRESH_FAILED" });
  expect(token).toEqual(prior());
  const unchanged = await sessionCallback({ session: { user: { id: "recipient" }, expires: "2099-01-01" }, token: failed } as Parameters<typeof sessionCallback>[0]) as Session;
  expect(unchanged.user.organizationId).toBeNull();
  expect(unchanged.user.role).toBe("researcher");
  expect(unchanged.accountRefreshError).toBe("ACCOUNT_REFRESH_FAILED");
});
