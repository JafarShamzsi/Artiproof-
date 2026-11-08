import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getSession } from "next-auth/react";

import { apiFetch } from "./api";

describe("apiFetch", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({}), { status: 200 }))
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("attaches the bearer token from the NextAuth session", async () => {
    vi.mocked(getSession).mockResolvedValueOnce({
      // The session shape used by next-auth callbacks in this app.
      accessToken: "test-token-123",
    } as unknown as Awaited<ReturnType<typeof getSession>>);

    await apiFetch("/api/auth/me");

    const call = vi.mocked(global.fetch).mock.calls[0];
    const init = call?.[1];
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer test-token-123");
    // JSON default Content-Type is set when no body is FormData.
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("omits the Authorization header when there is no session", async () => {
    vi.mocked(getSession).mockResolvedValueOnce(null);

    await apiFetch("/api/auth/me");

    const call = vi.mocked(global.fetch).mock.calls[0];
    const headers = new Headers(call?.[1]?.headers);
    expect(headers.get("Authorization")).toBeNull();
  });

  it("does NOT set Content-Type when the body is FormData", async () => {
    vi.mocked(getSession).mockResolvedValueOnce(null);
    const form = new FormData();
    form.append("file", new Blob(["x"], { type: "text/plain" }), "f.txt");

    await apiFetch("/api/source-check/upload", { method: "POST", body: form });

    const call = vi.mocked(global.fetch).mock.calls[0];
    const headers = new Headers(call?.[1]?.headers);
    // Browser sets multipart/form-data with the right boundary; we must not
    // pre-set Content-Type or fetch refuses to compute the boundary.
    expect(headers.get("Content-Type")).toBeNull();
  });
});
