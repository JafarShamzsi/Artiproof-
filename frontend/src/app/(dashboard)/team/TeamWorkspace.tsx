"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import {
  Users,
  Mail,
  Settings as SettingsIcon,
  History,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/utils";
import type { OrgDetail } from "./types";
import { MembersTab } from "./MembersTab";
import { InvitesTab } from "./InvitesTab";
import { SettingsTab } from "./SettingsTab";
import { AuditTab } from "./AuditTab";

/**
 * Tabbed root for the /team workspace.
 *
 * Tab state is mirrored in the URL search-param `?tab=members|invites|settings|audit`
 * so links and refreshes preserve the user's place. The active tab also
 * informs document focus management for keyboard users (a fresh tab
 * gets initial focus on its primary action).
 *
 * Org detail is fetched once on mount and re-fetched whenever a tab
 * commits a mutation — children call `refresh()` to bust the cached
 * shape (e.g. when an invite gets accepted the seat counts move).
 */

type TabKey = "members" | "invites" | "settings" | "audit";

const TABS: ReadonlyArray<{ key: TabKey; label: string; icon: typeof Users; adminOnly?: boolean }> = [
  { key: "members", label: "Members", icon: Users },
  { key: "invites", label: "Invites", icon: Mail, adminOnly: true },
  { key: "settings", label: "Settings", icon: SettingsIcon, adminOnly: true },
  { key: "audit", label: "Audit", icon: History, adminOnly: true },
];

export function TeamWorkspace() {
  const router = useRouter();
  const params = useSearchParams();
  const { data: session, status } = useSession();
  const [org, setOrg] = useState<OrgDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const orgId = (session as { user?: { organizationId?: string | null } } | null)
    ?.user?.organizationId ?? null;

  const tab: TabKey = useMemo(() => {
    const t = params?.get("tab");
    if (t === "invites" || t === "settings" || t === "audit") return t;
    return "members";
  }, [params]);

  const setTab = useCallback(
    (next: TabKey) => {
      const url = new URL(window.location.href);
      if (next === "members") url.searchParams.delete("tab");
      else url.searchParams.set("tab", next);
      router.replace(url.pathname + url.search, { scroll: false });
    },
    [router],
  );

  const fetchOrg = useCallback(async () => {
    if (!orgId) return;
    setError(null);
    try {
      const res = await apiFetch(`/api/organizations/${orgId}`);
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(data.detail || `Failed to load team (${res.status})`);
        return;
      }
      const body = (await res.json()) as OrgDetail;
      setOrg(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error");
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    if (status === "loading") return;
    if (status !== "authenticated") {
      router.replace("/login");
      return;
    }
    if (!orgId) {
      // Signed in but no team → bounce to settings where the user can
      // start a trial. Toast explains why.
      toast.info(
        "You aren't part of a team yet — head to Settings to start a 14-day trial.",
      );
      router.replace("/settings");
      return;
    }
    void fetchOrg();
  }, [status, orgId, fetchOrg, router]);

  const isAdmin = org?.current_user_role === "admin";

  if (loading || status === "loading") {
    return (
      <div className="flex items-center gap-3 py-20 text-fg-secondary">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span className="text-sm">Loading team…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
        <div className="flex items-center gap-2 text-red-700 dark:text-red-400">
          <AlertTriangle className="h-4 w-4" />
          <span className="text-sm font-medium">Couldn&apos;t load the team workspace</span>
        </div>
        <p className="mt-1 text-xs text-fg-secondary">{error}</p>
        <button
          type="button"
          onClick={() => void fetchOrg()}
          className="mt-3 rounded-md border border-border-default px-3 py-1.5 text-xs font-medium hover:bg-brand-soft"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!org) return null;

  const visibleTabs = TABS.filter((t) => !t.adminOnly || isAdmin);

  return (
    <div className="space-y-6">
      <Header org={org} isAdmin={isAdmin} />

      <nav
        aria-label="Team workspace sections"
        className="flex border-b border-border-default"
      >
        {visibleTabs.map((t) => {
          const active = t.key === tab;
          return (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setTab(t.key)}
              className={cn(
                "relative -mb-px inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "border-brand text-fg-primary"
                  : "border-transparent text-fg-secondary hover:text-fg-primary",
              )}
            >
              <t.icon className="h-4 w-4" aria-hidden="true" />
              {t.label}
            </button>
          );
        })}
      </nav>

      <div role="tabpanel">
        {tab === "members" && (
          <MembersTab
            orgId={org.id}
            currentUserId={session?.user?.email ?? ""}
            isAdmin={isAdmin}
            onMutate={fetchOrg}
          />
        )}
        {tab === "invites" && isAdmin && (
          <InvitesTab orgId={org.id} onMutate={fetchOrg} />
        )}
        {tab === "settings" && isAdmin && (
          <SettingsTab org={org} onMutate={fetchOrg} />
        )}
        {tab === "audit" && isAdmin && <AuditTab orgId={org.id} />}
      </div>
    </div>
  );
}

function Header({ org, isAdmin }: { org: OrgDetail; isAdmin: boolean }) {
  const pct = Math.min(100, Math.round((org.seat_used / org.seat_limit) * 100));
  const overCapWarn = org.seat_remaining <= 1;
  // The "days left" number depends on Date.now(), which the React purity
  // rule rightly flags as impure-in-render. We snapshot the value into
  // state once on mount so subsequent renders are deterministic; the
  // exact day count drifts by < 1 between mount and re-render and that's
  // fine for a banner.
  const [trialDaysLeft] = useState<number | null>(() =>
    org.trial_ends_at
      ? Math.max(
          0,
          Math.ceil(
            (new Date(org.trial_ends_at).getTime() - Date.now()) / 86_400_000,
          ),
        )
      : null,
  );

  return (
    <header className="rounded-lg border border-border-default bg-surface-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wider text-fg-tertiary">
            Team workspace
          </p>
          <h1 className="font-display text-2xl font-semibold text-fg-primary">
            {org.name}
          </h1>
          {org.slug && (
            <p className="mt-0.5 font-mono text-xs text-fg-tertiary">
              /{org.slug}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {org.is_trial && (
            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-700 dark:text-amber-300">
              Trial · {trialDaysLeft} {trialDaysLeft === 1 ? "day" : "days"} left
            </span>
          )}
          {isAdmin && (
            <Link
              href="/contact-sales?plan=team-upgrade"
              className="rounded-md border border-border-default px-3 py-1.5 text-xs font-medium text-fg-primary hover:bg-brand-soft"
            >
              Upgrade plan
            </Link>
          )}
        </div>
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between text-xs text-fg-secondary">
          <span>
            <span
              className={cn(
                "font-mono font-medium",
                overCapWarn ? "text-amber-700 dark:text-amber-300" : "text-fg-primary",
              )}
            >
              {org.seat_used}
            </span>{" "}
            of{" "}
            <span className="font-mono font-medium text-fg-primary">
              {org.seat_limit}
            </span>{" "}
            seats used
          </span>
          <span>{pct}%</span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={org.seat_used}
          aria-valuemin={0}
          aria-valuemax={org.seat_limit}
          aria-label="Team seat usage"
          className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-border-default"
        >
          <div
            className={cn(
              "h-full rounded-full transition-all",
              overCapWarn ? "bg-amber-500" : "bg-brand",
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </header>
  );
}
