"use client";

import { use, useCallback, useEffect, useState, useRef } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Users,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Share2,
  Download,
  BookOpen,
  GitBranch,
  ArrowLeft,
  Loader2,
  RefreshCw,
  Eye,
  EyeOff,
  History,
} from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";
import { useColorMode } from "@/contexts/ColorModeContext";

import { apiFetch } from "@/lib/api";
import { toast } from "@/lib/toast";
import { useReportActions } from "@/lib/useReportActions";
import { explainIntegrity } from "@/lib/scoreExplanation";
import { ScoreExplanationCard } from "@/components/ui/score-explanation";
import { scoreColor, scoreSolidBorderColor, scoreStroke } from "@/lib/colors";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { PinButton } from "@/components/ui/pin-button";
import type { ResearcherSnapshotItem, WatchlistEntry } from "@/types/api";

interface Publication {
  id: string;
  title: string;
  journal: string | null;
  year: number | null;
  doi: string | null;
  citation_count: number;
  suspicious_citations: number;
  topic_match_score: number | null;
  is_self_cited_heavily: boolean;
  flags: string[] | null;
}

interface GraphNode {
  id: string;
  name: string;
  type: string;
  citation_count: number;
}

interface GraphEdge {
  source: string;
  target: string;
  weight: number;
  papers: string[];
}

interface ProfileData {
  id: string;
  researcher_name: string;
  scopus_id: string | null;
  google_scholar_id: string | null;
  orcid: string | null;
  institution: string | null;
  official_h_index: number | null;
  official_citation_count: number | null;
  adjusted_h_index: number | null;
  adjusted_citation_count: number | null;
  integrity_score: number | null;
  self_citation_rate: number | null;
  citation_ring_flags: {
    rings?: Array<{
      members: Array<{ id: string; name: string; citations_to_target: number }>;
      total_mutual_citations: number;
      confidence: number;
    }>;
    suspicious_pairs?: Array<{
      author_id: string;
      author_name: string;
      citation_count: number;
      papers_cited: string[];
    }>;
    flags?: string[];
    graph?: { nodes: GraphNode[]; edges: GraphEdge[] };
  } | null;
  topic_relevance_score: number | null;
  analysis_status: string;
  last_analyzed_at: string | null;
  created_at: string;
  publications: Publication[];
}

export default function ResearcherResultPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [data, setData] = useState<ProfileData | null>(null);
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] } | null>(null);
  const [snapshots, setSnapshots] = useState<ResearcherSnapshotItem[]>([]);
  const [inWatchlist, setInWatchlist] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reAnalyzing, setReAnalyzing] = useState(false);
  const [watchlistBusy, setWatchlistBusy] = useState(false);

  // Single-shot fetch for the profile + graph + snapshots + watchlist on mount.
  // Each fetch is independent, so a failure on one (e.g. snapshots is fine
  // when there's no history) doesn't block the others.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [profileRes, graphRes, snapsRes, watchRes] = await Promise.all([
        apiFetch(`/api/researcher/${id}`),
        apiFetch(`/api/researcher/${id}/citation-graph`),
        apiFetch(`/api/researcher/${id}/snapshots`),
        apiFetch(`/api/me/watchlist`),
      ]);

      if (cancelled) return;

      if (!profileRes.ok) {
        setError("Not found");
        setLoading(false);
        return;
      }
      const profile = (await profileRes.json()) as ProfileData;
      const graph = graphRes.ok
        ? await graphRes.json()
        : { nodes: [], edges: [] };
      const snaps: ResearcherSnapshotItem[] = snapsRes.ok
        ? await snapsRes.json()
        : [];
      const watch: WatchlistEntry[] = watchRes.ok ? await watchRes.json() : [];

      if (cancelled) return;

      setData(profile);
      setGraphData(graph);
      setSnapshots(snaps);
      setInWatchlist(watch.some((e) => e.researcher_id === id));
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  // POSTing to /rerun returns the profile in pending state. We refetch to
  // pick up the freshly-reset analysis_status (and surface anything else the
  // orchestrator updated transactionally) — the URL stays put so any pins
  // and watchlist links remain valid.
  const handleReanalyze = useCallback(async () => {
    setReAnalyzing(true);
    try {
      const res = await apiFetch(`/api/researcher/${id}/rerun`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || "Failed to queue re-analysis");
        return;
      }
      toast.success("Re-analysis queued");
      // Refetch the profile so the UI reflects the pending status. Snapshots
      // get refreshed too so any newly captured row appears immediately.
      const [profileRes, snapsRes] = await Promise.all([
        apiFetch(`/api/researcher/${id}`),
        apiFetch(`/api/researcher/${id}/snapshots`),
      ]);
      if (profileRes.ok) {
        setData((await profileRes.json()) as ProfileData);
      }
      if (snapsRes.ok) {
        setSnapshots((await snapsRes.json()) as ResearcherSnapshotItem[]);
      }
    } catch {
      toast.error("Network error — please try again");
    } finally {
      setReAnalyzing(false);
    }
  }, [id]);

  const handleToggleWatchlist = useCallback(async () => {
    setWatchlistBusy(true);
    try {
      if (inWatchlist) {
        const res = await apiFetch(`/api/me/watchlist/${id}`, {
          method: "DELETE",
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          toast.error(err.detail || "Failed to remove from watchlist");
          return;
        }
        setInWatchlist(false);
        toast.success("Removed from watchlist");
      } else {
        const res = await apiFetch(`/api/me/watchlist/${id}`, {
          method: "POST",
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          toast.error(err.detail || "Failed to add to watchlist");
          return;
        }
        setInWatchlist(true);
        toast.success("Added to watchlist");
      }
    } catch {
      toast.error("Network error — please try again");
    } finally {
      setWatchlistBusy(false);
    }
  }, [id, inWatchlist]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-accent-amber" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <Link href="/researcher" className="flex items-center gap-1 text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white">
          <ArrowLeft className="h-4 w-4" /> Back
        </Link>
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardContent className="py-12 text-center">
            <p className="text-red-700 dark:text-red-400">Researcher profile not found.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const integrity = data.integrity_score ?? 0;
  const ringFlags = data.citation_ring_flags || {};
  const flags = ringFlags.flags || [];

  return (
    <ResearcherProfileView
      data={data}
      integrity={integrity}
      flags={flags}
      graphData={graphData}
      snapshots={snapshots}
      inWatchlist={inWatchlist}
      reAnalyzing={reAnalyzing}
      watchlistBusy={watchlistBusy}
      onReanalyze={handleReanalyze}
      onToggleWatchlist={handleToggleWatchlist}
    />
  );
}

const PUB_PAGE_SIZE = 20;

function ResearcherProfileView({
  data,
  integrity,
  flags,
  graphData,
  snapshots,
  inWatchlist,
  reAnalyzing,
  watchlistBusy,
  onReanalyze,
  onToggleWatchlist,
}: {
  data: ProfileData;
  integrity: number;
  flags: string[];
  graphData: { nodes: GraphNode[]; edges: GraphEdge[] } | null;
  snapshots: ResearcherSnapshotItem[];
  inWatchlist: boolean;
  reAnalyzing: boolean;
  watchlistBusy: boolean;
  onReanalyze: () => void;
  onToggleWatchlist: () => void;
}) {
  const { share, download, busy, copied, error } = useReportActions({
    researcherProfileId: data.id,
  });
  const [pubPage, setPubPage] = useState(0);
  const explanation = explainIntegrity({
    score: integrity,
    selfCitationRate: data.self_citation_rate,
    topicRelevanceScore: data.topic_relevance_score,
    flagCount: flags.length,
    publicationsCount: data.publications.length,
  });

  const totalPubs = data.publications.length;
  const lastPage = Math.max(0, Math.ceil(totalPubs / PUB_PAGE_SIZE) - 1);
  const pageStart = pubPage * PUB_PAGE_SIZE;
  const paginatedPublications = data.publications.slice(
    pageStart,
    pageStart + PUB_PAGE_SIZE,
  );

  return (
    <div className="space-y-6">
      <Breadcrumb
        items={[
          { label: "Dashboard", href: "/dashboard" },
          { label: "Researchers", href: "/researcher" },
          { label: "Result" },
        ]}
      />
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/researcher"
            aria-label="Back to researcher analyses"
            className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <h1 className="font-display text-2xl font-bold text-zinc-900 dark:text-white">Researcher Analysis</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <PinButton kind="researcher" id={data.id} />
          <Button
            variant="outline"
            size="sm"
            onClick={onToggleWatchlist}
            disabled={watchlistBusy}
            aria-pressed={inWatchlist}
            className="border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-400"
          >
            {watchlistBusy ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : inWatchlist ? (
              <EyeOff className="mr-1.5 h-4 w-4" />
            ) : (
              <Eye className="mr-1.5 h-4 w-4" />
            )}
            {inWatchlist ? "Remove from watchlist" : "Add to watchlist"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onReanalyze}
            disabled={reAnalyzing}
            className="border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-400"
          >
            {reAnalyzing ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-1.5 h-4 w-4" />
            )}
            Re-analyze
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={share}
            disabled={busy}
            className="border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-400"
          >
            {busy ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <Share2 className="mr-1.5 h-4 w-4" />
            )}
            {copied ? "Copied!" : "Share"}
          </Button>
          <Button
            size="sm"
            onClick={download}
            disabled={busy}
            className="bg-brand text-white hover:bg-brand-hover"
          >
            {busy ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <Download className="mr-1.5 h-4 w-4" />
            )}
            Report
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Status */}
      {data.analysis_status !== "completed" && (
        <Card className="border-blue-500/30 bg-blue-500/5">
          <CardContent className="flex items-center gap-3 py-4">
            {data.analysis_status === "processing" ? (
              <Loader2 className="h-5 w-5 animate-spin text-blue-700 dark:text-blue-400" />
            ) : (
              <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            )}
            <span className="text-sm text-zinc-700 dark:text-zinc-300">Status: {data.analysis_status}</span>
          </CardContent>
        </Card>
      )}

      {/* Profile Card */}
      <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
        <CardContent className="flex flex-col items-center gap-6 py-8 md:flex-row">
          <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full bg-accent-amber/15">
            <Users className="h-10 w-10 text-accent-amber" />
          </div>
          <div className="flex-1 text-center md:text-left">
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">{data.researcher_name}</h2>
            {data.institution && <p className="text-sm text-zinc-600 dark:text-zinc-400">{data.institution}</p>}
            <div className="mt-2 flex flex-wrap gap-2">
              {data.orcid && <Badge className="bg-zinc-500/20 text-zinc-700 dark:text-zinc-400">ORCID: {data.orcid}</Badge>}
              {data.publications.length > 0 && (
                <Badge className="bg-accent-amber/15 text-accent-amber">
                  {data.publications.length} publications
                </Badge>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Metrics Comparison + Integrity */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* Official Metrics */}
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="text-sm text-zinc-600 dark:text-zinc-400">Official Metrics</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">h-index</span>
              <span className="text-xl font-bold text-zinc-900 dark:text-white">{data.official_h_index ?? "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">Citations</span>
              <span className="text-xl font-bold text-zinc-900 dark:text-white">
                {data.official_citation_count?.toLocaleString() ?? "—"}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Adjusted Metrics */}
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-400">
              <TrendingUp className="h-4 w-4" /> Adjusted Metrics
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">h-index</span>
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold text-emerald-700 dark:text-emerald-400">{data.adjusted_h_index ?? "—"}</span>
                {data.official_h_index != null && data.adjusted_h_index != null && data.adjusted_h_index < data.official_h_index && (
                  <TrendingDown className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                )}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-600 dark:text-zinc-400">Citations</span>
              <span className="text-xl font-bold text-emerald-700 dark:text-emerald-400">
                {data.adjusted_citation_count?.toLocaleString() ?? "—"}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Integrity Score */}
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="text-sm text-zinc-600 dark:text-zinc-400">Integrity Score</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center">
            <div
              role="meter"
              aria-label="Integrity score"
              aria-valuenow={Math.round(integrity)}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuetext={`${Math.round(integrity)} out of 100`}
              className={`flex h-20 w-20 items-center justify-center rounded-full border-4 ${scoreColor(integrity)} ${scoreSolidBorderColor(integrity)}`}
            >
              <span className="text-2xl font-bold">{Math.round(integrity)}</span>
            </div>
            <div className="mt-3 space-y-1 text-center">
              {data.self_citation_rate != null && (
                <p className="text-xs text-zinc-500">
                  Self-citation: {(data.self_citation_rate * 100).toFixed(1)}%
                </p>
              )}
              {data.topic_relevance_score != null && (
                <p className="text-xs text-zinc-500">
                  Topic relevance: {(data.topic_relevance_score * 100).toFixed(0)}%
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Score explanation */}
      <ScoreExplanationCard explanation={explanation} />

      {/* Flags */}
      {flags.length > 0 && (
        <Card className="border-amber-500/20 bg-amber-500/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm text-amber-700 dark:text-amber-400">
              <AlertTriangle className="h-4 w-4" /> Integrity Flags ({flags.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {flags.map((flag: string, i: number) => (
              <div key={i} className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
                <p className="text-sm text-zinc-700 dark:text-zinc-300">{flag}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Citation Network */}
      {graphData && graphData.nodes.length > 1 && (
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
              <GitBranch className="h-4 w-4" /> Citation Network
            </CardTitle>
          </CardHeader>
          <CardContent>
            <CitationGraph nodes={graphData.nodes} edges={graphData.edges} />
          </CardContent>
        </Card>
      )}

      {/* Publications Table */}
      {data.publications.length > 0 && (
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
              <BookOpen className="h-4 w-4" /> Publications ({data.publications.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-200 text-left text-xs text-zinc-500 dark:border-zinc-800">
                    <th className="pb-2 pr-4">Title</th>
                    <th className="pb-2 pr-4">Journal</th>
                    <th className="pb-2 pr-4">Year</th>
                    <th className="pb-2 pr-4 text-right">Citations</th>
                    <th className="pb-2 pr-4 text-right">Topic Match</th>
                    <th className="pb-2">Flags</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedPublications.map((pub) => (
                    <tr key={pub.id} className="border-b border-zinc-200/70 dark:border-zinc-800/50">
                      <td className="max-w-[300px] truncate py-2 pr-4 text-zinc-900 dark:text-white">
                        {pub.doi ? (
                          <a
                            href={`https://doi.org/${pub.doi}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-brand hover:underline dark:hover:text-brand-fg"
                          >
                            {pub.title}
                          </a>
                        ) : (
                          pub.title
                        )}
                      </td>
                      <td className="max-w-[150px] truncate py-2 pr-4 text-zinc-600 dark:text-zinc-400">{pub.journal || "—"}</td>
                      <td className="py-2 pr-4 text-zinc-600 dark:text-zinc-400">{pub.year || "—"}</td>
                      <td className="py-2 pr-4 text-right text-zinc-700 dark:text-zinc-300">{pub.citation_count}</td>
                      <td className="py-2 pr-4 text-right">
                        {pub.topic_match_score != null ? (
                          <span className={
                            pub.topic_match_score >= 0.7 ? "text-emerald-700 dark:text-emerald-400"
                            : pub.topic_match_score >= 0.4 ? "text-amber-700 dark:text-amber-400"
                            : "text-red-700 dark:text-red-400"
                          }>
                            {(pub.topic_match_score * 100).toFixed(0)}%
                          </span>
                        ) : "—"}
                      </td>
                      <td className="py-2">
                        {pub.flags && pub.flags.length > 0 && (
                          <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {totalPubs > PUB_PAGE_SIZE && (
              <div className="mt-4 flex items-center justify-between border-t border-zinc-200 pt-3 text-xs dark:border-zinc-800">
                <button
                  type="button"
                  onClick={() => setPubPage((p) => Math.max(0, p - 1))}
                  disabled={pubPage === 0}
                  className="rounded-md border border-zinc-300 px-3 py-1.5 text-zinc-700 transition hover:border-zinc-400 hover:text-zinc-900 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:text-zinc-300 dark:hover:border-zinc-600 dark:hover:text-white"
                >
                  Previous
                </button>
                <span className="text-zinc-500">
                  {pageStart + 1}–{Math.min(pageStart + PUB_PAGE_SIZE, totalPubs)} of {totalPubs}
                </span>
                <button
                  type="button"
                  onClick={() => setPubPage((p) => Math.min(lastPage, p + 1))}
                  disabled={pubPage >= lastPage}
                  className="rounded-md border border-zinc-300 px-3 py-1.5 text-zinc-700 transition hover:border-zinc-400 hover:text-zinc-900 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:text-zinc-300 dark:hover:border-zinc-600 dark:hover:text-white"
                >
                  Next
                </button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* History — snapshots from prior re-analyses, newest first. */}
      <HistorySection snapshots={snapshots} />
    </div>
  );
}

// ─── History (re-analysis snapshots) ───────────────────────────────────

function HistorySection({ snapshots }: { snapshots: ResearcherSnapshotItem[] }) {
  return (
    <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
          <History className="h-4 w-4" /> History
        </CardTitle>
      </CardHeader>
      <CardContent>
        {snapshots.length === 0 ? (
          <p className="py-6 text-center text-sm text-zinc-500">
            No prior analyses recorded yet. Re-run the analysis to start
            building a timeline.
          </p>
        ) : (
          <div className="space-y-5">
            <SnapshotTrendChart snapshots={snapshots} />
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-zinc-200 text-left text-[11px] uppercase tracking-wide text-zinc-500 dark:border-zinc-800">
                    <th className="pb-2 pr-4 font-medium">Date</th>
                    <th className="pb-2 pr-4 text-right font-medium">Integrity</th>
                    <th className="pb-2 pr-4 text-right font-medium">Adj. h-index</th>
                    <th className="pb-2 text-right font-medium">Self-cite</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshots.map((s) => (
                    <tr
                      key={s.id}
                      className="border-b border-zinc-200/70 dark:border-zinc-800/50"
                    >
                      <td className="py-2 pr-4 text-zinc-700 dark:text-zinc-300">
                        {new Date(s.created_at).toLocaleString()}
                      </td>
                      <td
                        className={`py-2 pr-4 text-right font-bold tabular-nums ${scoreColor(s.integrity_score)}`}
                      >
                        {s.integrity_score != null
                          ? Math.round(s.integrity_score)
                          : "—"}
                      </td>
                      <td className="py-2 pr-4 text-right tabular-nums text-zinc-700 dark:text-zinc-300">
                        {s.adjusted_h_index ?? "—"}
                      </td>
                      <td className="py-2 text-right tabular-nums text-zinc-700 dark:text-zinc-300">
                        {s.self_citation_rate != null
                          ? `${(s.self_citation_rate * 100).toFixed(1)}%`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Compact integrity-score-over-time chart. Inline SVG: backend snapshots are
 * delivered newest-first, but the chart wants chronological order so we
 * reverse a copy here. The grid uses currentColor so it picks up the
 * surrounding text color in both light and dark themes without needing a
 * theme branch — keeps it simpler than the dashboard's TrendChart.
 */
function SnapshotTrendChart({
  snapshots,
}: {
  snapshots: ResearcherSnapshotItem[];
}) {
  const points = [...snapshots]
    .reverse()
    .filter((s) => s.integrity_score != null)
    .map((s) => ({ score: s.integrity_score as number, date: s.created_at }));

  if (points.length === 0) {
    return (
      <p className="py-2 text-center text-xs text-zinc-500">
        No scored snapshots yet — the next re-run will start the timeline.
      </p>
    );
  }

  const W = 600;
  const H = 180;
  const PAD = 35;
  const plotW = W - PAD * 2;
  const plotH = H - PAD * 2;
  const n = points.length;

  // Single point: render a tidy dot rather than a line of length zero.
  const xy = points.map((p, i) => ({
    x: n === 1 ? PAD + plotW / 2 : PAD + (i / (n - 1)) * plotW,
    y: PAD + plotH - (Math.max(0, Math.min(100, p.score)) / 100) * plotH,
    ...p,
  }));

  // Color the polyline by the latest score so the visual matches the gauge.
  const latestScore = points[n - 1].score;
  const lineHex = scoreStroke(latestScore);
  const pathD = xy.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`Integrity score over time, ${n} snapshot${n === 1 ? "" : "s"}`}
      className="w-full text-zinc-400 dark:text-zinc-600"
      style={{ maxHeight: 200 }}
    >
      {/* Grid lines + score labels — use currentColor so theme follows the
          parent text color without a useColorMode branch. */}
      {[0, 25, 50, 75, 100].map((v) => {
        const y = PAD + plotH - (v / 100) * plotH;
        return (
          <g key={v}>
            <line
              x1={PAD}
              y1={y}
              x2={W - PAD}
              y2={y}
              stroke="currentColor"
              strokeOpacity={0.35}
              strokeWidth={1}
            />
            <text
              x={PAD - 6}
              y={y + 4}
              textAnchor="end"
              fill="currentColor"
              fontSize={9}
            >
              {v}
            </text>
          </g>
        );
      })}

      {/* Score line — solid only when there are >= 2 points; for n=1 we still
          render the dot below. */}
      {n >= 2 && (
        <path
          d={pathD}
          fill="none"
          stroke={lineHex}
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}

      {xy.map((p, i) => (
        <g key={i}>
          <circle
            cx={p.x}
            cy={p.y}
            r={3.5}
            fill={scoreStroke(p.score)}
            stroke="currentColor"
            strokeWidth={1.5}
            strokeOpacity={0.6}
          />
          {(i === 0 || i === n - 1 || n <= 6) && (
            <text
              x={p.x}
              y={H - 4}
              textAnchor="middle"
              fill="currentColor"
              fontSize={8}
            >
              {new Date(p.date).toLocaleDateString("en", {
                month: "short",
                day: "numeric",
              })}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}

/**
 * SVG-based force-directed citation graph visualization.
 */
function CitationGraph({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  const { highContrast } = useTheme();
  const { resolved } = useColorMode();
  const isDark = resolved === "dark";
  const svgRef = useRef<SVGSVGElement>(null);
  const W = 700, H = 400;

  const colors = highContrast
    ? {
        target: "#FFEB00",
        targetStroke: "#FFFFFF",
        citer: "#00E5FF",
        citerStroke: "#FFFFFF",
        suspicious: "#FF6B00",
        suspiciousStroke: "#FFFFFF",
        edge: "#FFFFFF",
        edgeSuspicious: "#FF6B00",
        label: "#FFFFFF",
      }
    : isDark
    ? {
        target: "#E8AA42",     // accent-amber (dark)
        targetStroke: "#F5C77A",
        citer: "#10b981",
        citerStroke: "#34d399",
        suspicious: "#ef4444",
        suspiciousStroke: "#f87171",
        edge: "#3f3f46",
        edgeSuspicious: "#ef4444",
        label: "#a1a1aa",
      }
    : {
        target: "#A77416",     // accent-amber (light, slightly deeper for contrast)
        targetStroke: "#C8901E",
        citer: "#047857",
        citerStroke: "#059669",
        suspicious: "#dc2626",
        suspiciousStroke: "#ef4444",
        edge: "#d4d4d8",
        edgeSuspicious: "#dc2626",
        label: "#52525b",
      };

  // Simple circular layout — target in center, citers around
  const target = nodes.find((n) => n.type === "target");
  const citers = nodes.filter((n) => n.type !== "target");

  const positions: Record<string, { x: number; y: number }> = {};
  if (target) {
    positions[target.id] = { x: W / 2, y: H / 2 };
  }

  citers.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / citers.length;
    const radius = Math.min(W, H) * 0.35;
    positions[node.id] = {
      x: W / 2 + Math.cos(angle) * radius,
      y: H / 2 + Math.sin(angle) * radius,
    };
  });

  // Determine max weight for edge thickness scaling
  const maxWeight = Math.max(1, ...edges.map((e) => e.weight));

  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Citation network: ${nodes.length} authors, ${edges.length} citation relationships`}
        className="w-full"
        style={{ minHeight: 300, maxHeight: 450 }}
      >
        {/* Edges */}
        {edges.map((edge, i) => {
          const from = positions[edge.source];
          const to = positions[edge.target];
          if (!from || !to) return null;
          const isSuspicious = edge.weight >= 5;
          const thickness = 1 + (edge.weight / maxWeight) * 4;
          return (
            <line
              key={i}
              x1={from.x} y1={from.y}
              x2={to.x} y2={to.y}
              stroke={isSuspicious ? colors.edgeSuspicious : colors.edge}
              strokeWidth={highContrast ? thickness + 1 : thickness}
              strokeOpacity={highContrast ? 1 : isSuspicious ? 0.8 : 0.4}
            />
          );
        })}

        {/* Nodes */}
        {nodes.map((node) => {
          const pos = positions[node.id];
          if (!pos) return null;
          const isTarget = node.type === "target";
          const radius = isTarget ? 18 : 8 + Math.min(8, node.citation_count / 2);
          const isSuspicious = edges.some(
            (e) => e.source === node.id && e.weight >= 5
          );

          const ariaLabel = isTarget
            ? `Target researcher: ${node.name}`
            : `${node.name}, ${node.citation_count} citation${node.citation_count === 1 ? "" : "s"} to target${
                isSuspicious ? ", flagged as suspicious" : ""
              }`;

          // SVG focus rings: Safari ignores tabIndex on <g>, so put it on
          // the <circle> itself. Use focus-visible to widen the stroke as a
          // visible focus indicator (replacing the default outline that would
          // sit awkwardly on a circular shape).
          return (
            <g key={node.id}>
              <circle
                cx={pos.x}
                cy={pos.y}
                r={radius}
                role="button"
                tabIndex={0}
                aria-label={ariaLabel}
                fill={isTarget ? colors.target : isSuspicious ? colors.suspicious : colors.citer}
                fillOpacity={highContrast ? 1 : isTarget ? 1 : 0.7}
                stroke={isTarget ? colors.targetStroke : isSuspicious ? colors.suspiciousStroke : colors.citerStroke}
                strokeWidth={isTarget ? 3 : highContrast ? 2 : 1.5}
                className="cursor-pointer outline-none focus-visible:[stroke:#fbbf24] focus-visible:[stroke-width:4]"
                onKeyDown={(e) => {
                  // Reserved for future: open node detail on Enter / Space.
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                  }
                }}
              />
              {/* Label */}
              <text
                x={pos.x}
                y={pos.y + radius + 14}
                textAnchor="middle"
                fill={colors.label}
                fontSize={isTarget ? 11 : 9}
                fontWeight={isTarget ? 600 : highContrast ? 600 : 400}
              >
                {node.name.length > 18 ? node.name.slice(0, 16) + "..." : node.name}
              </text>
              {/* Citation count on hover area */}
              {!isTarget && (
                <title>
                  {node.name} — {node.citation_count} citation(s) to target
                </title>
              )}
            </g>
          );
        })}

        {/* Legend */}
        <g transform={`translate(16, ${H - 60})`}>
          <circle cx={0} cy={0} r={6} fill={colors.target} />
          <text x={12} y={4} fill={colors.label} fontSize={9}>Target Researcher</text>
          <circle cx={0} cy={18} r={5} fill={colors.citer} />
          <text x={12} y={22} fill={colors.label} fontSize={9}>Citing Author</text>
          <circle cx={0} cy={36} r={5} fill={colors.suspicious} />
          <text x={12} y={40} fill={colors.label} fontSize={9}>
            Flagged — unusually frequent citations
          </text>
        </g>
      </svg>
    </div>
  );
}
