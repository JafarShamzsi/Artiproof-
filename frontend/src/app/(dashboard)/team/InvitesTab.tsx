"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Mail, RotateCw, X } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/utils";
import type { OrgInvite, OrgInviteListResponse } from "./types";

/**
 * Invites tab — lists pending invites with resend and revoke.
 *
 * Pending invites are what the admin needs to act on; expired and
 * revoked rows are stored on the backend for the audit trail but not
 * shown here. The route layer marks rows expired on read so the list
 * stays accurate without a sweep job.
 *
 * `onMutate` is called after every resend/revoke so the parent can
 * refresh the seat-usage header — pending invites count toward the cap.
 */
export function InvitesTab({
  orgId,
  onMutate,
}: {
  orgId: string;
  onMutate: () => void;
}) {
  const [invites, setInvites] = useState<OrgInvite[]>([]);
  const [loading, setLoading] = useState(true);
  const [mutatingId, setMutatingId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch(`/api/organizations/${orgId}/invites`);
      if (res.ok) {
        const body = (await res.json()) as OrgInviteListResponse;
        setInvites(body.items);
      } else {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        toast.error(data.detail || "Failed to load invites");
      }
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function resend(invite: OrgInvite) {
    if (mutatingId === invite.id) return;
    setMutatingId(invite.id);
    try {
      const res = await apiFetch(
        `/api/organizations/${orgId}/invites/${invite.id}/resend`,
        { method: "POST" },
      );
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        toast.error(data.detail || "Resend failed");
        return;
      }
      toast.success(`Resent invite to ${invite.email}`);
    } finally {
      setMutatingId(null);
    }
  }

  async function revoke(invite: OrgInvite) {
    if (mutatingId === invite.id) return;
    if (!window.confirm(`Revoke the invite for ${invite.email}?`)) return;
    setMutatingId(invite.id);
    try {
      const res = await apiFetch(
        `/api/organizations/${orgId}/invites/${invite.id}`,
        { method: "DELETE" },
      );
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        toast.error(data.detail || "Revoke failed");
        return;
      }
      toast.success("Invite revoked");
      await reload();
      onMutate();
    } finally {
      setMutatingId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-fg-secondary">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading invites…
      </div>
    );
  }

  if (invites.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border-default p-8 text-center">
        <Mail className="mx-auto h-6 w-6 text-fg-tertiary" />
        <p className="mt-2 text-sm text-fg-primary">No pending invites</p>
        <p className="mt-1 text-xs text-fg-secondary">
          Use the Members tab to invite a new teammate.
        </p>
      </div>
    );
  }

  return (
    <ul className="divide-y divide-border-default overflow-hidden rounded-lg border border-border-default bg-surface-card">
      {invites.map((inv) => {
        const expiresIn = Math.max(
          0,
          Math.ceil((new Date(inv.expires_at).getTime() - Date.now()) / 86_400_000),
        );
        return (
          <li
            key={inv.id}
            className="flex flex-wrap items-center gap-3 px-4 py-3"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-fg-primary">
                  {inv.email}
                </span>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider",
                    inv.role === "admin"
                      ? "bg-brand/10 text-brand-fg"
                      : "bg-border-default text-fg-secondary",
                  )}
                >
                  {inv.role}
                </span>
              </div>
              <p className="mt-0.5 font-mono text-[10px] text-fg-tertiary">
                Invited {new Date(inv.created_at).toLocaleDateString()} · expires
                in {expiresIn} {expiresIn === 1 ? "day" : "days"}
              </p>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => resend(inv)}
                disabled={mutatingId === inv.id}
                className="inline-flex items-center gap-1.5 rounded-md border border-border-default px-2.5 py-1 text-xs font-medium text-fg-primary hover:bg-brand-soft disabled:cursor-not-allowed disabled:opacity-50"
              >
                {mutatingId === inv.id ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <RotateCw className="h-3 w-3" />
                )}
                Resend
              </button>
              <button
                type="button"
                onClick={() => revoke(inv)}
                disabled={mutatingId === inv.id}
                aria-label={`Revoke invite for ${inv.email}`}
                className="rounded-md border border-border-default p-1.5 text-fg-secondary hover:bg-red-500/10 hover:text-red-700 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:text-red-400"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
