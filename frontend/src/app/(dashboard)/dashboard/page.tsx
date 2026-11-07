"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Search,
  Users,
  Shield,
  TrendingUp,
  ArrowRight,
  Loader2,
  AlertTriangle,
  Sparkles,
  X,
  BarChart3,
  Filter,
  CheckCircle2,
  FileText,
  Compass,
} from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";
import { useColorMode } from "@/contexts/ColorModeContext";
import { apiFetch } from "@/lib/api";
import { scoreColor } from "@/lib/colors";
import { EmptyState } from "@/components/ui/empty-state";

type DateRange = "7d" | "30d" | "90d" | "all";
const RANGES: { value: DateRange; label: string }[] = [
  { value: "7d", label: "7d" },
  { value: "30d", label: "30d" },
  { value: "90d", label: "90d" },
  { value: "all", label: "All" },
];

const ONBOARDING_DISMISSED_KEY = "artiproof:onboarding-dismissed";

interface Stats {
  total_source_checks: number;
  avg_credibility_score: number;
  total_researcher_analyses: number;
  recent_alerts: number;
}

interface ActivityItem {
  id: string;
  type: string;
  title: string;
  status: string;
  score: number | null;
  created_at: string;
}

interface TrendPoint {
  date: string;
  score: number;
  count: number;
}

interface UsageBucket {
  used: number;
  limit: number | null;
  percent: number | null;
}

interface UsageData {
  tier: "free" | "pro" | "team";
  period_start: string;
  period_end: string;
  usage: {
    source_checks: UsageBucket;
    researcher_analyses: UsageBucket;
    reports: UsageBucket;
  };
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [range, setRange] = useState<DateRange>("30d");
  const [activitySearch, setActivitySearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Lazy initializer so SSR doesn't trip on localStorage and the very first
  // client paint already reflects whether the user dismissed the onboarding.
  const [onboardingDismissed, setOnboardingDismissed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    try {
      return localStorage.getItem(ONBOARDING_DISMISSED_KEY) === "true";
    } catch {
      return false;
    }
  });

  const load = useCallback(async (rangeParam: DateRange, signal?: AbortSignal) => {
    setError(null);
    setLoading(true);
    try {
      // Surface failures instead of swallowing them — partial dashboard
      // data with no indication is worse than a clear error.
      const [statsRes, activityRes, trendsRes, usageRes] = await Promise.all([
        apiFetch("/api/dashboard/stats", { signal }),
        apiFetch("/api/dashboard/recent-activity", { signal }),
        apiFetch(`/api/dashboard/trends?range=${rangeParam}`, { signal }),
        apiFetch("/api/dashboard/usage", { signal }),
      ]);
      if (!statsRes.ok || !activityRes.ok || !trendsRes.ok || !usageRes.ok) {
        throw new Error("Dashboard request failed");
      }
      const [s, a, t, u] = await Promise.all([
        statsRes.json(),
        activityRes.json(),
        trendsRes.json(),
        usageRes.json(),
      ]);
      setStats(s);
      setActivity(a || []);
      setTrends(t?.data || []);
      setUsage(u);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError(e instanceof Error ? e.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(range, controller.signal);
    return () => controller.abort();
  }, [load, range]);

  // Refetch only the trends when the range changes after initial load,
  // rather than re-running the whole dashboard every time. The full `load`
  // above handles the initial fetch + range; this is the cheap subsequent
  // path. We can't combine them because the initial render needs to know
  // every other tile too.
  const refetchTrends = useCallback(async (next: DateRange) => {
    setRange(next);
  }, []);

  const dismissOnboarding = useCallback(() => {
    try {
      localStorage.setItem(ONBOARDING_DISMISSED_KEY, "true");
    } catch {
      // ignore — we'll just show it again next session
    }
    setOnboardingDismissed(true);
  }, []);

  // Filter activity by free-form search. Type filter is implicit via the
  // string — "researcher" matches both the title and the type substring.
  const filteredActivity = useMemo(() => {
    const q = activitySearch.trim().toLowerCase();
    if (!q) return activity;
    return activity.filter(
      (item) =>
        item.title.toLowerCase().includes(q) || item.type.toLowerCase().includes(q),
    );
  }, [activity, activitySearch]);

  const showOnboarding =
    !onboardingDismissed &&
    stats != null &&
    stats.total_source_checks === 0 &&
    stats.total_researcher_analyses === 0;

  const showUsageWidget = usage != null && usage.tier !== "team";

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-brand dark:text-brand-fg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <AlertTriangle className="h-10 w-10 text-amber-600 dark:text-amber-400" />
        <p className="mt-4 max-w-sm text-sm text-zinc-700 dark:text-zinc-300">{error}</p>
        <Button
          onClick={() => load(range)}
          className="mt-4 bg-brand text-white hover:bg-brand-hover"
        >
          Try again
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">Dashboard</h1>

      {showOnboarding && <Onboarding onDismiss={dismissOnboarding} />}

      {showUsageWidget && <UsageWidget data={usage!} />}

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: "Source Checks", value: stats?.total_source_checks ?? 0, icon: Search, color: "text-brand dark:text-brand-fg", bg: "bg-brand/10" },
          { label: "Avg Credibility", value: stats?.avg_credibility_score ? `${stats.avg_credibility_score.toFixed(0)}` : "—", icon: TrendingUp, color: "text-fg-secondary", bg: "bg-border-subtle/40" },
          { label: "Researcher Analyses", value: stats?.total_researcher_analyses ?? 0, icon: Users, color: "text-accent-amber", bg: "bg-accent-amber/10" },
          { label: "Low Credibility Alerts", value: stats?.recent_alerts ?? 0, icon: AlertTriangle, color: "text-amber-700 dark:text-amber-400", bg: "bg-amber-500/10" },
        ].map((s) => (
          <Card key={s.label} className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
            <CardContent className="flex items-center gap-3 py-4">
              <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${s.bg}`}>
                <s.icon className={`h-5 w-5 ${s.color}`} />
              </div>
              <div>
                <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                <p className="text-xs text-zinc-500">{s.label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardContent className="py-8 text-center">
            <Search className="mx-auto mb-3 h-10 w-10 text-brand dark:text-brand-fg" />
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-white">Check a Source</h3>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              Verify articles, URLs, or documents for misinformation and AI-generated content.
            </p>
            <Link href="/check">
              <Button className="mt-4 bg-brand text-white hover:bg-brand-hover">
                Start Checking <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardContent className="py-8 text-center">
            <Users className="mx-auto mb-3 h-10 w-10 text-accent-amber" />
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-white">Analyze a Researcher</h3>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              Evaluate academic integrity, detect citation rings, and get adjusted metrics.
            </p>
            <Link href="/researcher">
              <Button className="mt-4 bg-accent-amber text-white hover:opacity-90">
                Start Analysis <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* Trends + Activity */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Trend Chart */}
        <Card className="border-zinc-200 bg-white lg:col-span-2 dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardHeader className="flex flex-row items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
              <TrendingUp className="h-4 w-4" /> Credibility Score Trend
            </CardTitle>
            <RangeSelector value={range} onChange={refetchTrends} />
          </CardHeader>
          <CardContent>
            {trends.length > 1 ? (
              <TrendChart data={trends} />
            ) : (
              <p className="py-8 text-center text-sm text-zinc-500">
                {range === "all"
                  ? "Run more source checks to see your credibility trend."
                  : `No scored checks in the last ${range}. Try widening the range.`}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardHeader className="space-y-2">
            <CardTitle className="text-sm text-zinc-600 dark:text-zinc-400">Recent Activity</CardTitle>
            {activity.length > 0 && (
              <div className="relative">
                <Filter
                  aria-hidden="true"
                  className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-400"
                />
                <Input
                  aria-label="Filter recent activity"
                  placeholder="Filter…"
                  value={activitySearch}
                  onChange={(e) => setActivitySearch(e.target.value)}
                  className="h-8 pl-7 pr-7 text-xs"
                />
                {activitySearch && (
                  <button
                    type="button"
                    aria-label="Clear filter"
                    onClick={() => setActivitySearch("")}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            )}
          </CardHeader>
          <CardContent className="space-y-3">
            {activity.length === 0 ? (
              <EmptyState
                icon={<Shield className="h-5 w-5" />}
                title="No activity yet"
                description="Run a source check or analyze a researcher to see activity here."
                action={{ label: "Start a check", href: "/check" }}
                className="py-8"
              />
            ) : filteredActivity.length === 0 ? (
              <p className="py-6 text-center text-xs text-zinc-500">
                No activity matches &ldquo;{activitySearch}&rdquo;.
              </p>
            ) : (
              filteredActivity.map((item) => (
                <Link
                  key={item.id}
                  href={item.type === "source_check" ? `/check/${item.id}` : `/researcher/${item.id}`}
                  className="block rounded-lg border border-zinc-200 px-3 py-2 transition hover:border-zinc-300 dark:border-zinc-800 dark:hover:border-zinc-700"
                >
                  <div className="flex items-start gap-2">
                    <div
                      aria-hidden="true"
                      className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                        item.status === "completed" ? "bg-emerald-500 dark:bg-emerald-400"
                        : item.status === "failed" ? "bg-red-500 dark:bg-red-400"
                        : "bg-blue-500 dark:bg-blue-400"
                      }`}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-xs font-medium text-zinc-700 dark:text-zinc-300">{item.title}</p>
                      <div className="flex items-center gap-2">
                        <p className="text-[10px] text-zinc-500">{timeAgo(item.created_at)}</p>
                        {/* Text label so the status is conveyed without relying on dot color */}
                        <span className="sr-only">Status: {item.status}</span>
                        <span
                          className={`text-[10px] uppercase tracking-wide ${
                            item.status === "completed" ? "text-emerald-700 dark:text-emerald-400"
                            : item.status === "failed" ? "text-red-700 dark:text-red-400"
                            : "text-blue-700 dark:text-blue-400"
                          }`}
                          aria-hidden="true"
                        >
                          {item.status}
                        </span>
                        {item.score !== null && (
                          <span className={`text-[10px] font-bold ${scoreColor(item.score)}`}>
                            {item.score.toFixed(0)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </Link>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function TrendChart({ data }: { data: TrendPoint[] }) {
  const { highContrast } = useTheme();
  const { resolved } = useColorMode();
  const isDark = resolved === "dark";
  const W = 600, H = 180, PAD = 35;
  const plotW = W - PAD * 2, plotH = H - PAD * 2;
  const n = data.length;
  if (n < 2) return null;
  const points = data.map((d, i) => ({
    x: PAD + (i / (n - 1)) * plotW,
    y: PAD + plotH - (d.score / 100) * plotH,
    ...d,
  }));
  const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
  const areaD = `${pathD} L ${points[n - 1].x} ${PAD + plotH} L ${points[0].x} ${PAD + plotH} Z`;

  // High-contrast mode wins; otherwise we pick palette by resolved color mode.
  const gridStroke = highContrast ? "#FFFFFF" : isDark ? "#27272a" : "#e4e4e7";
  const gridLabel = highContrast ? "#FFFFFF" : isDark ? "#52525b" : "#71717a";
  const line = highContrast ? "#FFEB00" : "#10b981";
  const pointStroke = highContrast ? "#000000" : isDark ? "#09090b" : "#ffffff";
  const scoreLabel = highContrast ? "#FFFFFF" : isDark ? "#a1a1aa" : "#52525b";
  const dateLabel = highContrast ? "#FFFFFF" : isDark ? "#52525b" : "#71717a";
  const gridWidth = highContrast ? 2 : 1;
  const lineWidth = highContrast ? 3 : 2;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 200 }}>
      {[0, 25, 50, 75, 100].map((v) => {
        const y = PAD + plotH - (v / 100) * plotH;
        return (
          <g key={v}>
            <line x1={PAD} y1={y} x2={W - PAD} y2={y} stroke={gridStroke} strokeWidth={gridWidth} />
            <text x={PAD - 6} y={y + 4} textAnchor="end" fill={gridLabel} fontSize={9}>{v}</text>
          </g>
        );
      })}
      <path d={areaD} fill="url(#trendFill)" opacity={highContrast ? 0.25 : 0.12} />
      <defs>
        <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={line} />
          <stop offset="100%" stopColor="transparent" />
        </linearGradient>
      </defs>
      <path d={pathD} fill="none" stroke={line} strokeWidth={lineWidth} strokeLinecap="round" strokeLinejoin="round" />
      {points.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r={highContrast ? 4.5 : 3.5} fill={line} stroke={pointStroke} strokeWidth={2} />
          <text x={p.x} y={p.y - 8} textAnchor="middle" fill={scoreLabel} fontSize={9} fontWeight={600}>
            {p.score.toFixed(0)}
          </text>
          {(i === 0 || i === n - 1 || n <= 6) && (
            <text x={p.x} y={H - 4} textAnchor="middle" fill={dateLabel} fontSize={8}>
              {new Date(p.date).toLocaleDateString("en", { month: "short", day: "numeric" })}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}


/* ───── Range selector for the trend chart ───── */

function RangeSelector({
  value,
  onChange,
}: {
  value: DateRange;
  onChange: (next: DateRange) => void;
}) {
  return (
    <div
      role="group"
      aria-label="Trend range"
      className="inline-flex rounded-md border border-zinc-200 bg-zinc-50 p-0.5 text-[11px] dark:border-zinc-800 dark:bg-zinc-900"
    >
      {RANGES.map((r) => {
        const active = r.value === value;
        return (
          <button
            key={r.value}
            type="button"
            onClick={() => onChange(r.value)}
            aria-pressed={active}
            className={`rounded px-2 py-1 font-medium transition ${
              active
                ? "bg-brand text-white shadow-sm"
                : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
            }`}
          >
            {r.label}
          </button>
        );
      })}
    </div>
  );
}


/* ───── Onboarding card — shown when the user has zero activity yet ───── */

function Onboarding({ onDismiss }: { onDismiss: () => void }) {
  return (
    <Card className="relative overflow-hidden border-brand/30 bg-brand-soft/50 dark:border-brand/40 dark:bg-brand/10">
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss welcome guide"
        className="absolute right-3 top-3 rounded-md p-1 text-fg-tertiary transition hover:bg-brand/10 hover:text-fg-primary"
      >
        <X className="h-4 w-4" />
      </button>
      <CardContent className="space-y-4 py-6">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-brand dark:text-brand-fg" />
          <h2 className="font-display text-lg font-semibold text-fg-primary">
            Welcome to ArtiProof
          </h2>
        </div>
        <p className="max-w-2xl text-sm text-fg-secondary">
          Three steps to get the most out of your account. Each one takes about
          a minute.
        </p>
        <ol className="grid gap-3 md:grid-cols-3">
          <OnboardingStep
            n={1}
            icon={<Search className="h-4 w-4" />}
            title="Run your first source check"
            body="Paste a URL, drop a PDF, or paste raw text. ArtiProof returns a credibility score with per-deduction reasoning."
            cta={{ label: "Check a source", href: "/check" }}
          />
          <OnboardingStep
            n={2}
            icon={<Users className="h-4 w-4" />}
            title="Analyze a researcher"
            body="Look up by ORCID or name. We compute self-citation, ring detection, and an adjusted h-index."
            cta={{ label: "Analyze researcher", href: "/researcher" }}
          />
          <OnboardingStep
            n={3}
            icon={<FileText className="h-4 w-4" />}
            title="Generate a report"
            body="Every check produces a downloadable PDF with the full breakdown — share it via a private link or save for the record."
            cta={{ label: "View reports", href: "/reports" }}
          />
        </ol>
        <p className="flex items-center gap-1.5 pt-1 text-[11px] text-fg-tertiary">
          <Compass className="h-3 w-3" />
          You can dismiss this any time — it won&apos;t come back unless you
          clear browser data.
        </p>
      </CardContent>
    </Card>
  );
}

function OnboardingStep({
  n,
  icon,
  title,
  body,
  cta,
}: {
  n: number;
  icon: React.ReactNode;
  title: string;
  body: string;
  cta: { label: string; href: string };
}) {
  return (
    <li className="rounded-lg border border-border-default bg-surface-card p-4 dark:border-zinc-800/80 dark:bg-zinc-900/40">
      <div className="flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand text-[11px] font-semibold text-white">
          {n}
        </span>
        <span className="text-fg-secondary">{icon}</span>
      </div>
      <h3 className="mt-3 text-sm font-semibold text-fg-primary">{title}</h3>
      <p className="mt-1 text-xs leading-relaxed text-fg-secondary">{body}</p>
      <Link
        href={cta.href}
        className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-brand hover:text-brand-hover dark:text-brand-fg"
      >
        {cta.label} <ArrowRight className="h-3 w-3" />
      </Link>
    </li>
  );
}


/* ───── Usage widget — month-to-date vs tier limits ───── */

function UsageWidget({ data }: { data: UsageData }) {
  const tierLabel =
    data.tier === "free" ? "Free plan" : data.tier === "pro" ? "Pro plan" : "Team plan";

  const buckets: { key: keyof UsageData["usage"]; label: string }[] = [
    { key: "source_checks", label: "Source checks" },
    { key: "researcher_analyses", label: "Researcher analyses" },
    { key: "reports", label: "Reports" },
  ];

  // Surface "approaching limit" only on the highest-percent bucket, so we
  // don't yell three times. Same reason free-tier users should know.
  const peak = buckets.reduce<{ percent: number; label: string } | null>(
    (acc, b) => {
      const bucket = data.usage[b.key];
      if (bucket.percent == null) return acc;
      if (acc == null || bucket.percent > acc.percent) {
        return { percent: bucket.percent, label: b.label };
      }
      return acc;
    },
    null,
  );
  const approaching =
    peak != null && peak.percent >= 75 && peak.percent < 100 ? peak : null;
  const reached =
    peak != null && peak.percent >= 100 ? peak : null;

  return (
    <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
          <BarChart3 className="h-4 w-4" /> Usage this month
          <span className="ml-1 rounded-md border border-border-default px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-fg-secondary">
            {tierLabel}
          </span>
        </CardTitle>
        {data.tier !== "team" && (
          <Link
            href="/settings"
            className="text-[11px] font-medium text-brand hover:text-brand-hover dark:text-brand-fg"
          >
            Manage plan →
          </Link>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {reached != null && (
          <div
            role="status"
            className="flex items-start gap-2 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300"
          >
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              You&apos;ve hit your monthly {reached.label.toLowerCase()} limit. New
              {" "}requests will be rejected until next month or you upgrade.
            </span>
          </div>
        )}
        {reached == null && approaching != null && (
          <div
            role="status"
            className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300"
          >
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              You&apos;re at {approaching.percent}% of your{" "}
              {approaching.label.toLowerCase()} quota.
            </span>
          </div>
        )}
        {buckets.map((b) => (
          <UsageRow key={b.key} label={b.label} bucket={data.usage[b.key]} />
        ))}
      </CardContent>
    </Card>
  );
}

function UsageRow({ label, bucket }: { label: string; bucket: UsageBucket }) {
  if (bucket.limit == null) {
    return (
      <div className="flex items-center justify-between text-xs">
        <span className="text-fg-secondary">{label}</span>
        <span className="flex items-center gap-1 text-fg-primary">
          <CheckCircle2 className="h-3 w-3 text-brand dark:text-brand-fg" />
          <span className="tabular-nums">{bucket.used}</span>
          <span className="text-fg-tertiary">used · unlimited</span>
        </span>
      </div>
    );
  }
  const percent = bucket.percent ?? 0;
  const barClass =
    percent >= 100
      ? "bg-red-500"
      : percent >= 75
        ? "bg-accent-amber"
        : "bg-brand";
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-fg-secondary">{label}</span>
        <span className="tabular-nums text-fg-primary">
          {bucket.used} / {bucket.limit}
          <span className="ml-1 text-fg-tertiary">({percent}%)</span>
        </span>
      </div>
      <div
        role="progressbar"
        aria-label={`${label} usage`}
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-1.5 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800"
      >
        <div
          className={`h-full rounded-full transition-all ${barClass}`}
          style={{ width: `${Math.min(100, percent)}%` }}
        />
      </div>
    </div>
  );
}
