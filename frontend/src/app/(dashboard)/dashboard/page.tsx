"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Search,
  Users,
  Shield,
  TrendingUp,
  ArrowRight,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";
import { useColorMode } from "@/contexts/ColorModeContext";
import { apiFetch } from "@/lib/api";
import { scoreColor } from "@/lib/colors";
import { EmptyState } from "@/components/ui/empty-state";

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

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setError(null);
    setLoading(true);
    try {
      // Surface failures instead of swallowing them — partial dashboard
      // data with no indication is worse than a clear error.
      const [statsRes, activityRes, trendsRes] = await Promise.all([
        apiFetch("/api/dashboard/stats", { signal }),
        apiFetch("/api/dashboard/recent-activity", { signal }),
        apiFetch("/api/dashboard/trends", { signal }),
      ]);
      if (!statsRes.ok || !activityRes.ok || !trendsRes.ok) {
        throw new Error("Dashboard request failed");
      }
      const [s, a, t] = await Promise.all([
        statsRes.json(),
        activityRes.json(),
        trendsRes.json(),
      ]);
      setStats(s);
      setActivity(a || []);
      setTrends(t?.data || []);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError(e instanceof Error ? e.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

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
          onClick={() => load()}
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
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
              <TrendingUp className="h-4 w-4" /> Credibility Score Trend
            </CardTitle>
          </CardHeader>
          <CardContent>
            {trends.length > 1 ? (
              <TrendChart data={trends} />
            ) : (
              <p className="py-8 text-center text-sm text-zinc-500">
                Run more source checks to see your credibility trend.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="text-sm text-zinc-600 dark:text-zinc-400">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {activity.length > 0 ? (
              activity.map((item) => (
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
            ) : (
              <EmptyState
                icon={<Shield className="h-5 w-5" />}
                title="No activity yet"
                description="Run a source check or analyze a researcher to see activity here."
                action={{ label: "Start a check", href: "/check" }}
                className="py-8"
              />
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
