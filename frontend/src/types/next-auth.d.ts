import "next-auth";

declare module "next-auth" {
  interface Session {
    accessToken?: string;
    user: {
      id: string;
      name?: string | null;
      email?: string | null;
      image?: string | null;
      role: string;
      institution?: string | null;
      // Tier + org are surfaced from the backend login response so the
      // dashboard layout can gate the /team sidebar entry without a
      // separate /api/auth/me round-trip on every render. Stale until
      // the user logs out and back in (24h JWT expiry); UI mutations
      // that change tier should refresh the session.
      tier?: string;
      organizationId?: string | null;
    };
  }

  interface User {
    role?: string;
    accessToken?: string;
    institution?: string | null;
    tier?: string;
    organizationId?: string | null;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    id: string;
    role: string;
    accessToken?: string;
    institution?: string | null;
    tier?: string;
    organizationId?: string | null;
  }
}
