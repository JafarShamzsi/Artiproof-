"use client";

import { useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";

type Invitation = { organization_id: string; name: string; role: string };

export function InvitationConsent({ token }: { token: string }) {
  const { data: session, status, update } = useSession();
  const accountId = session?.user?.id;
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    // The parent keys this instance by token/account. Obsolete requests may
    // finish, but must not update its successor or start a session refresh.
    return () => { active.current = false; };
  }, []);
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [enrolled, setEnrolled] = useState(false);

  async function submit(accept: boolean) {
    if (status !== "authenticated" || !accountId || busy) return;
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
      if (!active.current) return;
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
      if (active.current) {
        setMessage(error instanceof Error ? error.message : "Could not reach the server. Please try again.");
      }
    } finally {
      if (active.current) setBusy(false);
    }
  }

  async function synchronizeSession() {
    try {
      const refreshed = await update({ refreshAccount: true });
      if (!active.current) return;
      if (refreshed?.accountRefreshError || !refreshed?.user
          || refreshed.user.id !== accountId
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
      {status === "authenticated" && accountId ? (
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
      ) : status === "loading" ? (
        <p role="status">Checking session…</p>
      ) : status === "authenticated" ? (
        <p role="alert">Could not identify your account. Sign in again before reviewing this invitation.</p>
      ) : (
        <p>Create an account below, or <Link href="/login">sign in</Link> to your existing account. After signing in and verifying your email, reopen this invitation link to review and accept it.</p>
      )}
      {message && <p role="alert">{message}</p>}
    </section>
  );
}
