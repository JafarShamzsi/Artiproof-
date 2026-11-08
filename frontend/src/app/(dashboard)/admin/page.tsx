"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";

import { apiFetch } from "@/lib/api";
import { toast } from "@/lib/toast";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AlertTriangle, ChevronDown, Loader2, RefreshCw, Shield, Users } from "lucide-react";

interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  role: string;
  tier: string;
  organization_id: string | null;
  deactivated_at: string | null;
  deleted_at: string | null;
  created_at: string;
  email_verified_at: string | null;
}

interface UserListResponse {
  items: AdminUser[];
  total: number;
  page: number;
  page_size: number;
}

interface FailedPipeline {
  kind: "source_check" | "researcher_analysis";
  id: string;
  user_id: string;
  user_email: string | null;
  title: string | null;
  status: string;
  created_at: string;
  updated_at: string | null;
}

interface AdminStats {
  users_total: number;
  users_by_tier: Record<string, number>;
  users_by_role: Record<string, number>;
  source_checks_last_24h: number;
  source_check_failures_last_24h: number;
  researcher_analyses_last_24h: number;
  researcher_failures_last_24h: number;
  reports_last_24h: number;
}

const TIERS = ["free", "pro", "team"] as const;

export default function AdminPage() {
  const router = useRouter();
  const { data: session, status: sessionStatus } = useSession();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  // Debounced view of `search` — the only thing that actually feeds the
  // network. Typing fast in the input updates `search` immediately (so
  // the field stays responsive) but `debouncedSearch` only changes 300ms
  // after the user stops typing, so we send one request per intent
  // instead of one per keystroke.
  const debouncedSearch = useDebouncedValue(search, 300);
  const [tierFilter, setTierFilter] = useState<string>("");
  const [failed, setFailed] = useState<FailedPipeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  // While a PATCH against a specific user's tier is in flight, we hold
  // their id here. The dropdown trigger for that row gets disabled so
  // a second click can't fire a duplicate request (which would race
  // with the optimistic `reload()` that follows the first response).
  const [mutatingUserId, setMutatingUserId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), page_size: "20" });
    if (debouncedSearch) params.set("q", debouncedSearch);
    if (tierFilter) params.set("tier", tierFilter);

    const [statsRes, usersRes, failedRes] = await Promise.all([
      apiFetch("/api/admin/stats"),
      apiFetch(`/api/admin/users?${params.toString()}`),
      apiFetch("/api/admin/pipelines/failed?hours=72&limit=20"),
    ]);

    if (statsRes.status === 403 || usersRes.status === 403) {
      setForbidden(true);
      setLoading(false);
      return;
    }

    if (statsRes.ok) setStats((await statsRes.json()) as AdminStats);
    if (usersRes.ok) {
      const body = (await usersRes.json()) as UserListResponse;
      setUsers(body.items);
      setTotal(body.total);
    }
    if (failedRes.ok) setFailed((await failedRes.json()) as FailedPipeline[]);
    setLoading(false);
  }, [page, debouncedSearch, tierFilter]);

  useEffect(() => {
    if (sessionStatus === "loading") return;
    if (sessionStatus === "unauthenticated") {
      router.push("/login");
      return;
    }
    // Fire-and-forget — `reload` is stable via useCallback. The setState
    // writes happen inside reload's async body, after the effect has
    // returned, so React batches them across the response boundaries.
    void reload();
  }, [sessionStatus, reload, router]);

  // Client-side fast-fail when the session role is known to be non-admin —
  // avoids a flash of the page chrome before the 403 comes back. The
  // backend still enforces; this is purely a UX optimization.
  const sessionRole = (session as { user?: { role?: string } } | null)?.user?.role;
  if (sessionStatus === "authenticated" && sessionRole && sessionRole !== "admin") {
    return <ForbiddenView />;
  }

  if (forbidden) return <ForbiddenView />;

  const handleTierChange = async (userId: string, tier: string) => {
    // Guard against double-fire when the user clicks the dropdown twice
    // before the first PATCH resolves. Without this, two PATCHes race
    // each other AND the `reload()` that follows the first response.
    if (mutatingUserId === userId) return;
    setMutatingUserId(userId);
    try {
      const res = await apiFetch(`/api/admin/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ tier }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || "Tier change failed");
        return;
      }
      toast.success(`Tier updated to ${tier}`);
      await reload();
    } finally {
      setMutatingUserId(null);
    }
  };

  const handleRestore = async (userId: string) => {
    const res = await apiFetch(`/api/admin/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ restore: true }),
    });
    if (!res.ok) {
      toast.error("Restore failed");
      return;
    }
    toast.success("User restored");
    reload();
  };

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Admin" },
        ]}
      />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="h-6 w-6 text-brand" />
          <h1 className="font-display text-2xl font-bold text-zinc-900 dark:text-white">
            Admin
          </h1>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={reload}
          disabled={loading}
        >
          {loading ? (
            <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-1.5 h-4 w-4" />
          )}
          Refresh
        </Button>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Users"
            value={stats.users_total}
            sublabel={`Free ${stats.users_by_tier.free} · Pro ${stats.users_by_tier.pro} · Team ${stats.users_by_tier.team}`}
          />
          <StatCard
            label="Source checks (24h)"
            value={stats.source_checks_last_24h}
            sublabel={`${stats.source_check_failures_last_24h} failed`}
            danger={stats.source_check_failures_last_24h > 0}
          />
          <StatCard
            label="Researcher analyses (24h)"
            value={stats.researcher_analyses_last_24h}
            sublabel={`${stats.researcher_failures_last_24h} failed`}
            danger={stats.researcher_failures_last_24h > 0}
          />
          <StatCard label="Reports (24h)" value={stats.reports_last_24h} />
        </div>
      )}

      {/* Users */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
            <Users className="h-4 w-4" /> Users ({total})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <Input
              value={search}
              onChange={(e) => {
                setPage(1);
                setSearch(e.target.value);
              }}
              placeholder="Search email or name"
              className="max-w-xs"
            />
            <DropdownMenu>
              <DropdownMenuTrigger className="inline-flex h-9 items-center rounded-md border border-zinc-300 px-3 text-sm font-medium hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800">
                Tier: {tierFilter || "all"}{" "}
                <ChevronDown className="ml-1 h-3 w-3" />
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                <DropdownMenuItem onClick={() => setTierFilter("")}>
                  all
                </DropdownMenuItem>
                {TIERS.map((t) => (
                  <DropdownMenuItem key={t} onClick={() => setTierFilter(t)}>
                    {t}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 text-left text-xs uppercase tracking-wide text-zinc-500 dark:border-zinc-800">
                  <th className="py-2 pr-4">Email</th>
                  <th className="py-2 pr-4">Name</th>
                  <th className="py-2 pr-4">Role</th>
                  <th className="py-2 pr-4">Tier</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Created</th>
                  <th className="py-2 pr-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.length === 0 && !loading && (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-zinc-500">
                      No users match.
                    </td>
                  </tr>
                )}
                {users.map((u) => (
                  <tr
                    key={u.id}
                    className="border-b border-zinc-100 hover:bg-zinc-50 dark:border-zinc-800/50 dark:hover:bg-zinc-800/30"
                  >
                    <td className="py-2 pr-4 font-mono text-xs text-zinc-700 dark:text-zinc-300">
                      {u.email}
                    </td>
                    <td className="py-2 pr-4">{u.full_name}</td>
                    <td className="py-2 pr-4">
                      <Badge>{u.role}</Badge>
                    </td>
                    <td className="py-2 pr-4">
                      {/* While this row's PATCH is in flight the trigger
                          is disabled so a stray second click can't fire
                          a duplicate request; the spinner replaces the
                          tier text so it's visible the action is mid-flight. */}
                      <DropdownMenu>
                        <DropdownMenuTrigger
                          disabled={mutatingUserId === u.id}
                          className="inline-flex items-center gap-1 rounded border border-zinc-300 px-2 py-0.5 text-xs hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:hover:bg-zinc-800"
                        >
                          {mutatingUserId === u.id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <>
                              {u.tier} <ChevronDown className="h-3 w-3" />
                            </>
                          )}
                        </DropdownMenuTrigger>
                        <DropdownMenuContent>
                          {TIERS.map((t) => (
                            <DropdownMenuItem
                              key={t}
                              onClick={() => handleTierChange(u.id, t)}
                              disabled={t === u.tier || mutatingUserId === u.id}
                            >
                              {t}
                            </DropdownMenuItem>
                          ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                    <td className="py-2 pr-4">
                      {u.deleted_at ? (
                        <Badge className="bg-red-500/20 text-red-700 dark:text-red-400">
                          deleted
                        </Badge>
                      ) : u.deactivated_at ? (
                        <Badge className="bg-amber-500/20 text-amber-700 dark:text-amber-400">
                          deactivated
                        </Badge>
                      ) : (
                        <Badge className="bg-emerald-500/20 text-emerald-700 dark:text-emerald-400">
                          active
                        </Badge>
                      )}
                    </td>
                    <td className="py-2 pr-4 text-xs text-zinc-500">
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-2 pr-4 text-right">
                      {u.deleted_at && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleRestore(u.id)}
                        >
                          Restore
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {total > users.length && (
            <div className="mt-4 flex items-center justify-between text-xs text-zinc-500">
              <span>
                Page {page} of {Math.ceil(total / 20)}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  Prev
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page * 20 >= total}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Failed pipelines */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
            <AlertTriangle className="h-4 w-4" /> Recent failures ({failed.length})
            <span className="ml-2 text-xs text-zinc-400">last 72h</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {failed.length === 0 ? (
            <p className="text-sm text-zinc-500">No pipeline failures in the window.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {failed.map((row) => (
                <li
                  key={`${row.kind}-${row.id}`}
                  className="flex items-center justify-between rounded border border-zinc-200 px-3 py-2 dark:border-zinc-800"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{row.kind.replace("_", " ")}</Badge>
                      <span className="truncate text-zinc-900 dark:text-zinc-100">
                        {row.title || "(untitled)"}
                      </span>
                    </div>
                    <div className="mt-0.5 text-xs text-zinc-500">
                      {row.user_email || row.user_id} ·{" "}
                      {new Date(row.created_at).toLocaleString()}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  label,
  value,
  sublabel,
  danger = false,
}: {
  label: string;
  value: number;
  sublabel?: string;
  danger?: boolean;
}) {
  return (
    <Card>
      <CardContent className="py-4">
        <div className="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
        <div
          className={`mt-1 text-2xl font-bold tabular-nums ${danger ? "text-amber-700 dark:text-amber-400" : "text-zinc-900 dark:text-white"}`}
        >
          {value.toLocaleString()}
        </div>
        {sublabel && (
          <div className="mt-1 text-xs text-zinc-500">{sublabel}</div>
        )}
      </CardContent>
    </Card>
  );
}

function ForbiddenView() {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-2 text-center">
      <Shield className="h-8 w-8 text-zinc-400" />
      <h2 className="font-display text-lg text-zinc-900 dark:text-white">
        Admin role required
      </h2>
      <p className="text-sm text-zinc-500">
        This page is restricted to users with the admin role.
      </p>
    </div>
  );
}
