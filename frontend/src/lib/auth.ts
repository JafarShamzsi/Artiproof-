import { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";

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
    created_at: string;
  };
}

interface BackendChallengeResponse {
  challenge: "totp";
  challenge_token: string;
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
          accessToken: tokenData.access_token,
        };
      },
    }),
    ...(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET
      ? [
          GoogleProvider({
            clientId: process.env.GOOGLE_CLIENT_ID!,
            clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
          }),
        ]
      : []),
  ],
  callbacks: {
    async jwt({ token, user, account }) {
      if (user) {
        token.id = user.id as string;
        token.role = (user as { role?: string }).role || "researcher";
        token.institution = (user as { institution?: string | null }).institution ?? null;
        token.accessToken = (user as { accessToken?: string }).accessToken;
      }

      if (account?.provider === "google" && account.id_token) {
        const res = await fetch(`${BACKEND_URL}/api/auth/google`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id_token: account.id_token }),
        });

        if (!res.ok) {
          throw new Error("Google sign-in failed");
        }

        const data = (await res.json()) as BackendTokenResponse;
        token.id = data.user.id;
        token.role = data.user.role || "researcher";
        token.institution = data.user.institution ?? null;
        token.accessToken = data.access_token;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.id as string;
        session.user.role = (token.role as string) || "researcher";
        session.user.institution = (token.institution as string | null) ?? null;
      }
      session.accessToken = token.accessToken as string | undefined;
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
