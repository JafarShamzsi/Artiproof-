import { afterEach, expect, it, vi } from "vitest";
import { authOptions } from "./auth";

const jwt = authOptions.callbacks!.jwt!;
type Args = Parameters<typeof jwt>[0];
const args = (idToken: string | undefined = "synthetic-id-token") => ({
  token: { id: "prior", accessToken: "prior-bearer" },
  user: { id: "google-sub", name: "Google name", email: "google@example.com" },
  account: { provider: "google", id_token: idToken },
} as Args);
const backend = { access_token: "synthetic-platform-bearer", token_type: "bearer",
  user: { id: "platform-user", email: "platform@example.com", full_name: "Platform name",
    institution: null, role: "researcher", tier: "free", organization_id: null } };
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

it("exchanges a Google ID token only on the server and uses platform identity", async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => backend });
  vi.stubGlobal("fetch", fetch);
  const input = args();
  const result = await jwt(input);
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/auth/google"), expect.objectContaining({
    method: "POST", body: JSON.stringify({ id_token: "synthetic-id-token" }), cache: "no-store",
  }));
  expect(result).toMatchObject({ id: "platform-user", name: "Platform name", email: "platform@example.com",
    accessToken: "synthetic-platform-bearer", role: "researcher", tier: "free", organizationId: null });
  expect(input.token).toEqual({ id: "prior", accessToken: "prior-bearer" });
});

it.each(["missing-id", "http", "network", "challenge", "malformed"])("fails closed on %s without mutating a session", async (failure) => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => {
    if (failure === "network") throw new Error("sensitive-provider-error-not-for-logs");
    return { ok: failure !== "http", json: async () => failure === "challenge"
      ? { challenge: "totp", challenge_token: "synthetic-challenge" } : { user: {} } };
  }));
  const input = args();
  if (failure === "missing-id") input.account!.id_token = undefined;
  await expect(jwt(input)).rejects.toThrow("Google sign-in failed");
  expect(input.token).toEqual({ id: "prior", accessToken: "prior-bearer" });
});

it("advertises Google only when both server OAuth settings exist", async () => {
  for (const configured of [false, true]) {
    vi.resetModules();
    vi.stubEnv("GOOGLE_CLIENT_ID", "synthetic.apps.googleusercontent.com");
    vi.stubEnv("GOOGLE_CLIENT_SECRET", configured ? "synthetic-secret" : "");
    const { authOptions: options } = await import("./auth");
    expect(options.providers.some(p => p.id === "google")).toBe(configured);
  }
});
