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
 * Fetch from the backend with the current user's JWT attached.
 *
 * - Adds `Authorization: Bearer <token>` when a NextAuth session exists.
 * - Preserves caller-provided headers (incl. Content-Type) but defaults to JSON.
 * - On 401, signs out and redirects to /login — treat every 401 as "session dead".
 *
 * Pass a FormData body to skip the default JSON Content-Type (fetch sets multipart/form-data automatically).
 */
export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const session = await getSession();
  const isFormData =
    typeof FormData !== "undefined" && options.body instanceof FormData;

  const headers = new Headers(options.headers);
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const accessToken = (session as { accessToken?: string } | null)?.accessToken;
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const res = await fetch(`${BACKEND_URL}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401 && typeof window !== "undefined") {
    // Token expired or invalid — boot back to login.
    await signOut({ callbackUrl: "/login", redirect: true });
  }

  return res;
}

/**
 * Back-compat export — existing code can keep calling `fetchFromBackend` and get JWT behavior.
 */
export const fetchFromBackend = apiFetch;
