"use client";

import { useCallback, useEffect, useState } from "react";
import {
  History,
  Loader2,
  Mail,
  MailX,
  RotateCw,
  Settings as SettingsIcon,
  UserMinus,
  UserPlus,
  UsersRound,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { OrgAuditLogItem, OrgAuditLogResponse } from "./types";

/**
 * Audit tab — paginated newest-first list of every org-management
 * action. The icon + human description for each row is derived from
 * `action` + `payload`. Unknown actions render as the raw label so a
 * forward-compat row (e.g. a new action shipped in a later release)
 * still shows up rather than vanishing.
 */
export function AuditTab({ orgId }: { orgId: string }) {
  const [items, setItems] = useState<OrgAuditLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const pageSize = 50;

  const reload = useCallback(
    async (nextPage: number) => {
      setLoading(true);
      try {
        const res = await apiFetch(
          `/api/organizations/${orgId}/audit-log?page=${nextPage}&page_size=${pageSize}`,
        );
        if (res.ok) {
          const body = (await res.json()) as OrgAuditLogResponse;
          setItems(body.items);
          setTotal(body.total);
        }
      } finally {
        setLoading(false);
      }
    },
    [orgId],
  );

  useEffect(() => {
    void reload(page);
  }, [reload, page]);

  if (loading && items.length === 0) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-fg-secondary">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading audit log…
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border-default p-8 text-center">
        <History className="mx-auto h-6 w-6 text-fg-tertiary" />
        <p className="mt-2 text-sm text-fg-primary">No team actions yet</p>
        <p className="mt-1 text-xs text-fg-secondary">
          Every invite, role change, and removal is recorded here.
        </p>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-3">
      <ul className="divide-y divide-border-default overflow-hidden rounded-lg border border-border-default bg-surface-card">
        {items.map((row) => (
          <li key={row.id} className="flex items-start gap-3 px-4 py-3">
            <ActionIcon action={row.action} />
            <div className="min-w-0 flex-1">
              <p className="text-sm text-fg-primary">
                <ActionDescription row={row} />
              </p>
              <p className="mt-0.5 font-mono text-[10px] text-fg-tertiary">
                {new Date(row.created_at).toLocaleString()}
              </p>
            </div>
          </li>
        ))}
      </ul>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-xs text-fg-secondary">
          <span>
            Page {page} of {totalPages} · {total} entries
          </span>
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="rounded-md border border-border-default px-2.5 py-1 hover:bg-brand-soft disabled:cursor-not-allowed disabled:opacity-50"
            >
              ← Newer
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages || loading}
              className="rounded-md border border-border-default px-2.5 py-1 hover:bg-brand-soft disabled:cursor-not-allowed disabled:opacity-50"
            >
              Older →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ActionIcon({ action }: { action: string }) {
  const Icon =
    action === "invite_sent" || action === "invite_resent"
      ? Mail
      : action === "invite_revoked"
        ? MailX
        : action === "member_added"
          ? UserPlus
          : action === "member_removed"
            ? UserMinus
            : action === "role_changed"
              ? UsersRound
              : action === "org_settings_changed" || action === "seat_limit_changed"
                ? SettingsIcon
                : action === "org_created"
                  ? RotateCw
                  : History;
  return (
    <span
      aria-hidden="true"
      className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-brand-soft text-brand-fg"
    >
      <Icon className="h-3.5 w-3.5" />
    </span>
  );
}

function ActionDescription({ row }: { row: OrgAuditLogItem }) {
  const actor = (
    <strong className="font-medium text-fg-primary">
      {row.actor_email ?? "Someone"}
    </strong>
  );
  const target = (
    <strong className="font-medium text-fg-primary">
      {row.target_email ?? (row.payload.email as string | undefined) ?? "a member"}
    </strong>
  );
  const role = (row.payload.role as string | undefined) ?? "member";

  switch (row.action) {
    case "invite_sent":
      return (
        <>
          {actor} invited {target} as {role}
        </>
      );
    case "invite_resent":
      return (
        <>
          {actor} re-sent the invite to {target}
        </>
      );
    case "invite_revoked":
      return (
        <>
          {actor} revoked the invite for {target}
        </>
      );
    case "member_added":
      return (
        <>
          {target} joined the team as {role}
        </>
      );
    case "member_removed":
      return (
        <>
          {actor} removed {target}
        </>
      );
    case "role_changed": {
      const from = (row.payload.from_role as string | undefined) ?? "?";
      const to = (row.payload.to_role as string | undefined) ?? "?";
      return (
        <>
          {actor} changed {target}&apos;s role from {from} to {to}
        </>
      );
    }
    case "org_settings_changed": {
      const fields = (row.payload.fields as string[] | undefined) ?? [];
      return (
        <>
          {actor} updated team settings ({fields.join(", ") || "no fields"})
        </>
      );
    }
    case "org_created":
      return (
        <>
          {actor} created the team
        </>
      );
    default:
      return (
        <>
          {actor} — {row.action}
        </>
      );
  }
}
