import { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";
import type { JWT } from "next-auth/jwt";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

interface BackendTokenResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    full_name: string;
    institution: string | null;
    role: string;
    tier: string;
    organization_id: string | null;
    created_at: string;
  };
}

interface BackendChallengeResponse {
  challenge: "totp";
  challenge_token: string;
}

export class AccountRefreshError extends Error {
  readonly code = "ACCOUNT_REFRESH_FAILED";
  constructor() {
    super("Session refresh failed. Reopen the invitation or sign in again before continuing.");
    this.name = "AccountRefreshError";
  }
}

async function refreshAccount(token: JWT): Promise<JWT> {
  // Never consume account/tier/role/token values supplied to update() by a
  // browser. The current server-held bearer identifies the authoritative user.
  if (!token.accessToken || !token.id) throw new AccountRefreshError();
  try {
    const response = await fetch(`${BACKEND_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token.accessToken}` }, cache: "no-store",
    });
    if (!response.ok) throw new AccountRefreshError();
    const data = await response.json();
    if (!data || data.id !== token.id || typeof data.email !== "string"
        || typeof data.full_name !== "string"
        || !["researcher", "faculty", "admin"].includes(data.role)
        || !["free", "pro", "team"].includes(data.tier)
        || !(data.institution === null || typeof data.institution === "string")
        || !(data.organization_id === null || (typeof data.organization_id === "string" && data.organization_id.length > 0))
        || (data.organization_id !== null && !["admin", "member"].includes(data.org_role))) {
      throw new AccountRefreshError();
    }
    // Copy only after full validation. Failure must not partially mutate the
    // prior session, or persist client-provided authorization fields.
    return { ...token, accountRefreshError: undefined, name: data.full_name, email: data.email, role: data.role,
      institution: data.institution, tier: data.tier, organizationId: data.organization_id };
  } catch {
    throw new AccountRefreshError();
  }
}

/**
 * Marker shape encoded into the Error message thrown from `authorize()` when
 * the backend issues a 2FA challenge. The login page parses this on the
 * client to render the second-step form. Kept JSON-encoded because NextAuth
 * v4 surfaces the raw `Error.message` when `redirect: false` is used.
 */
export interface TwoFactorChallengePayload {
  twoFactorChallenge: true;
  challengeToken: string;
}

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
        // Step-2 inputs — only present when re-submitting after a TOTP challenge.
        challengeToken: { label: "Challenge token", type: "text" },
        twoFactorCode: { label: "2FA code", type: "text" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          throw new Error("Email and password are required");
        }

        // ── Step 2: user is finishing a 2FA challenge ──
        if (credentials.challengeToken && credentials.twoFactorCode) {
          const res = await fetch(`${BACKEND_URL}/api/auth/login/2fa`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              challenge_token: credentials.challengeToken,
              code: credentials.twoFactorCode,
            }),
          });

          if (!res.ok) {
            const data = (await res.json().catch(() => ({}))) as { detail?: string };
            throw new Error(data.detail || "Invalid 2FA code");
          }

          const data = (await res.json()) as BackendTokenResponse;
          return {
            id: data.user.id,
            email: data.user.email,
            name: data.user.full_name,
            role: data.user.role,
            institution: data.user.institution,
            tier: data.user.tier,
            organizationId: data.user.organization_id,
            accessToken: data.access_token,
          };
        }

        // ── Step 1: email + password ──
        const res = await fetch(`${BACKEND_URL}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: credentials.email,
            password: credentials.password,
          }),
        });

        if (!res.ok) {
          throw new Error("Invalid email or password");
        }

        const data = (await res.json()) as BackendTokenResponse | BackendChallengeResponse;

        if ("challenge" in data) {
          // Surface the challenge token to the client by encoding it in the
          // error message — NextAuth v4 with `redirect: false` returns the
          // raw `Error.message` as `result.error`.
          const payload: TwoFactorChallengePayload = {
            twoFactorChallenge: true,
            challengeToken: data.challenge_token,
          };
          throw new Error(JSON.stringify(payload));
        }

        const tokenData: BackendTokenResponse = data;
        return {
          id: tokenData.user.id,
          email: tokenData.user.email,
          name: tokenData.user.full_name,
          role: tokenData.user.role,
          institution: tokenData.user.institution,
          tier: tokenData.user.tier,
          organizationId: tokenData.user.organization_id,
          accessToken: tokenData.access_token,
        };
      },
    }),
    ...(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET
      ? [
          GoogleProvider({
            clientId: process.env.GOOGLE_CLIENT_ID!,
            clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
            checks: ["pkce", "state", "nonce"],
          }),
        ]
      : []),
  ],
  events: {
    async signOut(message) {
      if (!("token" in message)) return;
      const accessToken = message.token?.accessToken;
      if (typeof accessToken !== "string" || !accessToken) return;
      try {
        const response = await fetch(`${BACKEND_URL}/api/auth/logout`, {
          method: "POST", headers: { Authorization: `Bearer ${accessToken}` },
          cache: "no-store", redirect: "error", signal: AbortSignal.timeout(5000),
        });
        // 401 already means the signed bearer is no longer usable.
        if (response.status !== 204 && response.status !== 401) throw new Error();
      } catch {
        // Always allow local cookie logout. No payload, bearer, URL or error
        // chain in logs. A failed revoke can leave copies valid until expiry.
        console.warn("Backend session revocation failed; local sign-out continues.");
      }
    },
  },
  callbacks: {
    async jwt({ token, user, account, trigger }) {
      if (trigger === "update") {
        try {
          return await refreshAccount(token);
        } catch {
          // Throwing here makes NextAuth v4 delete the session cookie. Keep
          // all prior authorization fields and expose a typed failure marker.
          return { ...token, accountRefreshError: "ACCOUNT_REFRESH_FAILED" };
        }
      }
      if (account?.provider === "google") {
        try {
          if (!account.id_token) throw new Error();
          const res = await fetch(`${BACKEND_URL}/api/auth/google`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id_token: account.id_token }),
            cache: "no-store",
          });
          if (!res.ok) throw new Error();
          const data = (await res.json()) as BackendTokenResponse;
          if (typeof data?.access_token !== "string" || !data.access_token
              || typeof data.user?.id !== "string" || !data.user.id
              || typeof data.user.email !== "string" || !data.user.email
              || typeof data.user.full_name !== "string"
              || !["researcher", "faculty", "admin"].includes(data.user.role)
              || !["free", "pro", "team"].includes(data.user.tier)
              || !(data.user.institution === null || typeof data.user.institution === "string")
              || !(data.user.organization_id === null || typeof data.user.organization_id === "string")) {
            throw new Error();
          }
          // No partial mutation, Google subject masquerading as platform ID,
          // or second-factor challenge masquerading as an authenticated session.
          return { ...token, id: data.user.id, name: data.user.full_name,
            email: data.user.email, role: data.user.role,
            institution: data.user.institution, tier: data.user.tier,
            organizationId: data.user.organization_id, accessToken: data.access_token };
        } catch {
          // Never leak provider payloads, ID tokens or transport errors to logs/UI.
          throw new Error("Google sign-in failed");
        }
      }
      if (user) {
        token.id = user.id as string;
        token.role = (user as { role?: string }).role || "researcher";
        token.institution = (user as { institution?: string | null }).institution ?? null;
        token.tier = (user as { tier?: string }).tier ?? "free";
        token.organizationId =
          (user as { organizationId?: string | null }).organizationId ?? null;
        token.accessToken = (user as { accessToken?: string }).accessToken;
      }

      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.id as string;
        session.user.role = (token.role as string) || "researcher";
        session.user.institution = (token.institution as string | null) ?? null;
        session.user.tier = (token.tier as string) ?? "free";
        session.user.organizationId =
          (token.organizationId as string | null) ?? null;
      }
      session.accessToken = token.accessToken as string | undefined;
      session.accountRefreshError = token.accountRefreshError;
      return session;
    },
  },
  pages: {
    signIn: "/login",
    error: "/login",
  },
  session: {
    strategy: "jwt",
  },
  secret: process.env.NEXTAUTH_SECRET,
};
