"use client";

import { useState } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";

type Invitation = { organization_id: string; name: string; role: string };

export function InvitationConsent({ token }: { token: string }) {
  const { status, update } = useSession();
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [enrolled, setEnrolled] = useState(false);

  async function submit(accept: boolean) {
    setBusy(true);
    setMessage("");
    try {
      if (accept && enrolled) {
        await synchronizeSession();
        return;
      }
      const path = accept && invitation
        ? `/api/organizations/${encodeURIComponent(invitation.organization_id)}/invites/accept`
        : "/api/organizations/invites/preview";
      const response = await apiFetch(path, { method: "POST", body: JSON.stringify({ token }) });
      const data = await response.json();
      if (!response.ok) {
        setMessage(typeof data.detail === "string" ? data.detail : "Invitation unavailable");
      } else if (accept) {
        // Enrollment may already be committed even if the following refresh
        // fails. Retry synchronization, not the mutation, in that case.
        setEnrolled(true);
        await synchronizeSession();
      } else {
        setInvitation(data);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not reach the server. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function synchronizeSession() {
    try {
      const refreshed = await update({ refreshAccount: true });
      if (refreshed?.accountRefreshError || !refreshed?.user
          || refreshed.user.organizationId !== invitation?.organization_id) {
        throw new Error("Session refresh failed");
      }
      setAccepted(true);
    } catch {
      throw new Error("Team enrollment was recorded, but session refresh failed. Retry session refresh or sign in again before continuing.");
    }
  }

  return (
    <section aria-label="Team invitation" className="space-y-3 rounded-lg border p-4">
      <h2 className="font-semibold">Team invitation</h2>
      <p>Opening this link does not join a team. Your personal and previous-team activity stays separate.</p>
      {status === "authenticated" ? (
        accepted ? (
          <p role="status">Invitation accepted. <Link href="/team">Continue to team</Link></p>
        ) : (
          <>
            <p>Verify your account email before joining. If needed, request verification in <Link href="/settings">Settings</Link>, then reopen this invitation.</p>
            {invitation ? (
              <>
                <p>Join <strong>{invitation.name}</strong> as {invitation.role}. New work created in this team is organization-owned and visible to its administrators; activity may appear in the team feed according to your sharing setting.</p>
                <Button type="button" disabled={busy} onClick={() => void submit(true)}>{enrolled ? "Retry session refresh" : "Accept invitation and join team"}</Button>
              </>
            ) : (
              <Button type="button" disabled={busy} onClick={() => void submit(false)}>Review invitation</Button>
            )}
          </>
        )
      ) : (
        <p>Create an account below, or <Link href="/login">sign in</Link> to your existing account. After signing in and verifying your email, reopen this invitation link to review and accept it.</p>
      )}
      {message && <p role="alert">{message}</p>}
    </section>
  );
}
