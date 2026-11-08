import { TeamWorkspace } from "./TeamWorkspace";

export const metadata = {
  title: "Team — ArtiProof",
  description:
    "Manage your team — members, invites, settings, and the audit log.",
};

/**
 * Team workspace page.
 *
 * The server component is intentionally thin — the entire surface is
 * client-side because every tab depends on the user's NextAuth session
 * (org id) and live data. The `TeamWorkspace` component handles the
 * "no org → redirect to settings" case so visiting `/team` without a
 * team-tier session lands somewhere sensible instead of a 404.
 */
export default function TeamPage() {
  return <TeamWorkspace />;
}
