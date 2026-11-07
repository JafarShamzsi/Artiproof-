import { getSession, signOut } from "next-auth/react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

/**
 * Build a backend URL for a public resource (PDF, download).
 * Used for <a href> and <img src> where we can't attach headers.
 */
export function backendUrl(path: string): string {
  return `${BACKEND_URL}${path}`;
}

/**
 * Extra options for `apiFetch` beyond the standard `RequestInit`.
 *
 * `skipAuthRedirect` opts out of the auto-signout on 401 — required for any
 * route where the backend uses 401 as a domain error (e.g. "current password
 * is incorrect" on the password / deactivate / delete endpoints) rather than
 * "session is dead". Without this, every wrong-password attempt would boot
 * the user to /login and discard their typed dialog state.
 */
export interface ApiFetchOptions extends RequestInit {
  skipAuthRedirect?: boolean;
}

/**
 * Fetch from the backend with the current user's JWT attached.
 *
 * - Adds `Authorization: Bearer <token>` when a NextAuth session exists.
 * - Preserves caller-provided headers (incl. Content-Type) but defaults to JSON.
 * - On 401, signs out and redirects to /login — treat every 401 as "session dead",
 *   unless `skipAuthRedirect: true` is passed (settings password-confirmed mutations).
 *
 * Pass a FormData body to skip the default JSON Content-Type (fetch sets multipart/form-data automatically).
 */
export async function apiFetch(
  path: string,
  options: ApiFetchOptions = {}
): Promise<Response> {
  const { skipAuthRedirect, ...fetchOptions } = options;
  const session = await getSession();
  const isFormData =
    typeof FormData !== "undefined" && fetchOptions.body instanceof FormData;

  const headers = new Headers(fetchOptions.headers);
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const accessToken = (session as { accessToken?: string } | null)?.accessToken;
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const res = await fetch(`${BACKEND_URL}${path}`, {
    ...fetchOptions,
    headers,
  });

  if (res.status === 401 && !skipAuthRedirect && typeof window !== "undefined") {
    // Token expired or invalid — boot back to login.
    await signOut({ callbackUrl: "/login", redirect: true });
  }

  return res;
}

/**
 * Back-compat export — existing code can keep calling `fetchFromBackend` and get JWT behavior.
 */
export const fetchFromBackend = apiFetch;
