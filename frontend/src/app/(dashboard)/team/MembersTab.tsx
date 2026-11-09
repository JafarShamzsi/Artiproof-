"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Mail, Trash2, UserPlus } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/utils";
import type {
  OrgMember,
  OrgMemberListResponse,
  OrgRole,
} from "./types";

/**
 * Members tab — list + invite-by-email + role change + remove.
 *
 * Lifted from the old `OrgMembersSection` in `settings/page.tsx`. The
 * invite form lives at the top of the tab so the most-common action
 * (Add someone) is one click away. Role changes and removals require
 * the caller to be admin; non-admins see a read-only roster.
 */
export function MembersTab({
  orgId,
  isAdmin,
  onMutate,
}: {
  orgId: string;
  currentUserId: string;
  isAdmin: boolean;
  onMutate: () => void;
}) {
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<OrgRole>("member");
  const [inviting, setInviting] = useState(false);
  const [mutatingUserId, setMutatingUserId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch(`/api/organizations/${orgId}/members`);
      if (res.ok) {
        const body = (await res.json()) as OrgMemberListResponse;
        setMembers(body.items);
      } else {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        toast.error(data.detail || "Failed to load members");
      }
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    const email = inviteEmail.trim();
    if (!email || inviting) return;
    setInviting(true);
    try {
      const res = await apiFetch(
        `/api/organizations/${orgId}/members/invite`,
        {
          method: "POST",
          body: JSON.stringify({ email, role: inviteRole }),
        },
      );
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        toast.error(data.detail || "Invite failed");
        return;
      }
      const body = (await res.json()) as {
        invited_email: string;
        status: "added" | "invited";
      };
      toast.success(
        body.status === "added"
          ? `${body.invited_email} added to the team`
          : `Invite sent to ${body.invited_email}`,
      );
      setInviteEmail("");
      setInviteRole("member");
      await reload();
      onMutate();
    } finally {
      setInviting(false);
    }
  }

  async function changeRole(userId: string, role: OrgRole) {
    if (mutatingUserId === userId) return;
    setMutatingUserId(userId);
    try {
      const res = await apiFetch(
        `/api/organizations/${orgId}/members/${userId}`,
        { method: "PATCH", body: JSON.stringify({ role }) },
      );
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        toast.error(data.detail || "Role change failed");
        return;
      }
      toast.success(`Role updated to ${role}`);
      await reload();
      onMutate();
    } finally {
      setMutatingUserId(null);
    }
  }

  async function remove(userId: string, email: string) {
    if (mutatingUserId === userId) return;
    if (
      !window.confirm(
        `Remove ${email} from the team? They lose access immediately but their work is retained.`,
      )
    ) {
      return;
    }
    setMutatingUserId(userId);
    try {
      const res = await apiFetch(
        `/api/organizations/${orgId}/members/${userId}`,
        { method: "DELETE" },
      );
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        toast.error(data.detail || "Remove failed");
        return;
      }
      toast.success("Member removed");
      await reload();
      onMutate();
    } finally {
      setMutatingUserId(null);
    }
  }

  return (
    <div className="space-y-4">
      {isAdmin && (
        <form
          onSubmit={invite}
          aria-label="Invite a new member"
          className="flex flex-wrap items-end gap-2 rounded-lg border border-border-default bg-surface-card p-4"
        >
          <div className="min-w-[220px] flex-1">
            <label
              htmlFor="team-invite-email"
              className="text-xs font-medium text-fg-secondary"
            >
              Invite by email
            </label>
            <input
              id="team-invite-email"
              type="email"
              required
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="colleague@example.com"
              className="mt-1 block w-full rounded-md border border-border-default bg-surface-base px-3 py-2 text-sm text-fg-primary placeholder:text-fg-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
            />
          </div>
          <div>
            <label
              htmlFor="team-invite-role"
              className="text-xs font-medium text-fg-secondary"
            >
              Role
            </label>
            <select
              id="team-invite-role"
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as OrgRole)}
              className="mt-1 block rounded-md border border-border-default bg-surface-base px-3 py-2 text-sm text-fg-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={inviting}
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-brand px-4 text-sm font-medium text-white shadow-sm shadow-brand/30 hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-60"
          >
            {inviting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <UserPlus className="h-4 w-4" />
            )}
            Send invite
          </button>
        </form>
      )}

      {loading ? (
        <div className="flex items-center gap-2 py-6 text-sm text-fg-secondary">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading members…
        </div>
      ) : members.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border-default p-8 text-center text-sm text-fg-secondary">
          Just you so far — invite a teammate above.
        </div>
      ) : (
        <ul className="divide-y divide-border-default overflow-hidden rounded-lg border border-border-default bg-surface-card">
          {members.map((m) => (
            <li
              key={m.user_id}
              className="flex flex-wrap items-center gap-3 px-4 py-3"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-fg-primary">
                    {m.full_name || m.email}
                  </span>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider",
                      m.role === "admin"
                        ? "bg-brand/10 text-brand-fg"
                        : "bg-border-default text-fg-secondary",
                    )}
                  >
                    {m.role}
                  </span>
                </div>
                <p className="mt-0.5 truncate text-xs text-fg-secondary">
                  <Mail className="mr-1 inline h-3 w-3" />
                  {m.email}
                </p>
                <p className="mt-1 font-mono text-[10px] text-fg-tertiary">
                  MTD — checks: {m.source_checks_mtd} · researchers:{" "}
                  {m.researcher_analyses_mtd} · reports: {m.reports_mtd}
                </p>
              </div>
              {isAdmin && (
                <div className="flex items-center gap-1.5">
                  <select
                    aria-label={`Change ${m.email}'s role`}
                    value={m.role}
                    onChange={(e) =>
                      changeRole(m.user_id, e.target.value as OrgRole)
                    }
                    disabled={mutatingUserId === m.user_id}
                    className="rounded-md border border-border-default bg-surface-base px-2 py-1 text-xs disabled:opacity-50"
                  >
                    <option value="member">Member</option>
                    <option value="admin">Admin</option>
                  </select>
                  <button
                    type="button"
                    onClick={() => remove(m.user_id, m.email)}
                    disabled={mutatingUserId === m.user_id}
                    aria-label={`Remove ${m.email}`}
                    className="rounded-md border border-border-default p-1.5 text-fg-secondary hover:bg-red-500/10 hover:text-red-700 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:text-red-400"
                  >
                    {mutatingUserId === m.user_id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
