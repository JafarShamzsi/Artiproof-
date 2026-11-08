"use client";

import { use, useEffect, useState, useRef, useCallback, lazy, Suspense } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Shield,
  Brain,
  BookOpen,
  Share2,
  Download,
  CheckCircle,
  XCircle,
  AlertTriangle,
  HelpCircle,
  Loader2,
  ArrowLeft,
  RefreshCw,
  Link2,
  ChevronDown,
  Copy,
  Trash2,
  FileJson,
  FileSpreadsheet,
} from "lucide-react";
import type { PdfViewerHandle } from "@/components/pdf-viewer";

const PdfViewer = lazy(() => import("@/components/pdf-viewer"));

import { apiFetch } from "@/lib/api";
import { analysisIsActive, useAnalysisRefresh } from "@/hooks/use-analysis-refresh";
import { useReportActions } from "@/lib/useReportActions";
import { explainCredibility } from "@/lib/scoreExplanation";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import {
  aiProbColor,
  scoreColor,
  scoreSolidBorderColor,
} from "@/lib/colors";
import {
  ScoreExplanationCompact,
} from "@/components/ui/score-explanation";
import { PinButton } from "@/components/ui/pin-button";
import { toast } from "@/lib/toast";
import {
  FullWidthView,
  type AIDetection,
  type CitationData,
  type ClaimData,
  type FullWidthSourceCheckData,
  type ModelMetadataData,
  type ScoreBreakdownData,
} from "@/components/source-check/FullWidthView";

// ── Types — extends the shared shape with fields the authed view needs (input_content, share_token). ──

interface SourceCheckData extends FullWidthSourceCheckData {
  input_content: string;
  /** Public share token — null when no link has been issued yet. */
  share_token: string | null;
}

interface PositionMap {
  claims: Record<string, { page: number; highlights: { bbox: number[]; page: number }[] }>;
  ai_detections: Record<string, { page: number; highlights: { bbox: number[]; page: number }[] }>;
  citations: Record<string, { page: number; highlights: { bbox: number[]; page: number }[] }>;
}

// ── Constants ──

const VERDICT_CONFIG: Record<
  string,
  { icon: typeof CheckCircle; color: string; bg: string; label: string }
> = {
  true: { icon: CheckCircle, color: "text-emerald-700 dark:text-emerald-400", bg: "bg-emerald-500/20", label: "True" },
  false: { icon: XCircle, color: "text-red-700 dark:text-red-400", bg: "bg-red-500/20", label: "False" },
  misleading: { icon: AlertTriangle, color: "text-amber-700 dark:text-amber-400", bg: "bg-amber-500/20", label: "Misleading" },
  partially_true: { icon: AlertTriangle, color: "text-yellow-700 dark:text-yellow-400", bg: "bg-yellow-500/20", label: "Partially True" },
  unverified: { icon: HelpCircle, color: "text-zinc-600 dark:text-zinc-400", bg: "bg-zinc-500/20", label: "Unverified" },
};

// ── Page Component ──

export default function SourceCheckResultPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [data, setData] = useState<SourceCheckData | null>(null);
  const [positionMap, setPositionMap] = useState<PositionMap | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pdfViewerRef = useRef<PdfViewerHandle>(null);

  const refreshResult = useCallback(async (result: SourceCheckData, signal: AbortSignal) => {
    // Annotations can become available after the initial pending response.
    if (!analysisIsActive(result.status) && result.has_pdf) {
      try {
        const response = await apiFetch(`/api/source-check/${id}/position-map`, { signal });
        const positions = response.ok ? await response.json() : null;
        if (!signal.aborted) setPositionMap(positions);
      } catch { /* The result remains useful without PDF navigation. */ }
    }
    if (!signal.aborted) setData(result);
  }, [id]);
  const refreshError = useAnalysisRefresh(
    `/api/source-check/${id}`, data?.id === id && analysisIsActive(data.status), refreshResult,
  );

  useEffect(() => {
    // Reset on every id change so navigating between two checks doesn't
    // flash the previous result's claims/citations while the new fetch
    // resolves. The lint rule fires for the first setData(null) only —
    // the others are recognized as part of the same reset cluster.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setData(null);
    setPositionMap(null);
    setError(null);
    setLoading(true);

    let cancelled = false;
    apiFetch(`/api/source-check/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error("Not found");
        return r.json();
      })
      .then((d) => {
        if (cancelled) return;
        setData(d);
        // Load position map if PDF
        if (d.has_pdf) {
          apiFetch(`/api/source-check/${id}/position-map`)
            .then((r) => (r.ok ? r.json() : null))
            .then((pm) => {
              if (!cancelled) setPositionMap(pm);
            })
            .catch(() => {});
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const handleFindingClick = (type: "claims" | "ai_detections" | "citations", findingId: string) => {
    if (!positionMap || !pdfViewerRef.current) return;
    const mapping = positionMap[type]?.[findingId];
    if (!mapping || !mapping.highlights?.length) return;
    const hl = mapping.highlights[0];
    pdfViewerRef.current.scrollToPosition(hl.page, hl.bbox);
  };

  if (loading) {
    // Skeleton mirroring the FullWidthView layout — score card, claims
    // card, citations card. Feels less jarring than a single spinner and
    // hints at the report structure before it loads.
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading source check">
        <div className="h-7 w-48 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardContent className="flex flex-col items-center gap-6 py-8 md:flex-row">
            <div className="h-28 w-28 shrink-0 animate-pulse rounded-full bg-zinc-200 dark:bg-zinc-800" />
            <div className="flex flex-1 flex-col gap-3">
              <div className="h-5 w-3/4 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
              <div className="h-3 w-1/2 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
              <div className="flex gap-2">
                <div className="h-6 w-20 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
                <div className="h-6 w-20 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
                <div className="h-6 w-24 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
              </div>
            </div>
          </CardContent>
        </Card>
        {[0, 1, 2].map((i) => (
          <Card key={i} className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
            <CardContent className="space-y-3 py-6">
              <div className="h-4 w-32 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
              <div className="h-3 w-full animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
              <div className="h-3 w-5/6 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (error || !data) {
    // Recoverable error state — back to /check (the list), plus a retry
    // that re-runs the same fetch. The previous "not found" message left
    // the user no path forward when a transient 5xx blew up the fetch.
    return (
      <div className="space-y-4">
        <Link href="/check" className="flex items-center gap-1 text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white">
          <ArrowLeft className="h-4 w-4" /> Back to checks
        </Link>
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardContent className="py-12 text-center">
            <AlertTriangle className="mx-auto h-10 w-10 text-amber-600 dark:text-amber-400" />
            <h2 className="mt-3 text-base font-semibold text-zinc-900 dark:text-white">
              Couldn&rsquo;t load this source check
            </h2>
            <p className="mt-1 text-sm text-zinc-500">
              {error === "Not found"
                ? "The check may have been deleted, or you may not have permission to view it."
                : "Something went wrong fetching this report. The error has been logged."}
            </p>
            <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
              <Button onClick={() => window.location.reload()} variant="outline">
                <RefreshCw className="mr-2 h-4 w-4" /> Try again
              </Button>
              <Link href="/check">
                <Button>Browse past checks</Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const isPdf = data.has_pdf;
  // Same-origin proxy so pdf.js (which can't set Authorization headers)
  // can load the authenticated backend PDF through our Next.js route.
  const pdfUrl = data.has_annotated_pdf
    ? `/api/pdf/source-check/${id}/annotated`
    : data.has_pdf
      ? `/api/pdf/source-check/${id}/original`
      : null;

  // Split-view for PDFs, full-width for URL/text
  if (isPdf && pdfUrl) {
    return (
      <>
      {refreshError && <p role="alert" className="mb-4 text-sm text-amber-700 dark:text-amber-300">{refreshError}</p>}
      <SplitView
        data={data}
        pdfUrl={pdfUrl}
        positionMap={positionMap}
        pdfViewerRef={pdfViewerRef}
        onFindingClick={handleFindingClick}
        onShareTokenChange={(token) => setData({ ...data, share_token: token })}
      />
      </>
    );
  }

  return (
    <>
    {refreshError && <p role="alert" className="mb-4 text-sm text-amber-700 dark:text-amber-300">{refreshError}</p>}
    <FullWidthView
      data={data}
      actionsSlot={
        <ActionButtons
          data={data}
          onShareTokenChange={(token) => setData({ ...data, share_token: token })}
        />
      }
    />
    </>
  );
}

// ── Action button cluster (Pin · Re-check · Share link · Export ▾ · Report) ──

function ActionButtons({
  data,
  onShareTokenChange,
}: {
  data: SourceCheckData;
  onShareTokenChange: (token: string | null) => void;
}) {
  const router = useRouter();
  const [rerunBusy, setRerunBusy] = useState(false);
  const [shareBusy, setShareBusy] = useState(false);
  const { share, download, busy: reportBusy, copied, error: reportError } =
    useReportActions({ sourceCheckId: data.id });
  const [exportBusy, setExportBusy] = useState<"json" | "csv" | null>(null);

  const handleRerun = useCallback(async () => {
    if (rerunBusy) return;
    setRerunBusy(true);
    try {
      const res = await apiFetch(`/api/source-check/${data.id}/rerun`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || `Re-check failed (HTTP ${res.status})`);
        return;
      }
      const newCheck = await res.json();
      toast.success("Re-check started");
      router.push(`/check/${newCheck.id}`);
    } catch {
      toast.error("Network error — please try again");
    } finally {
      setRerunBusy(false);
    }
  }, [data.id, rerunBusy, router]);

  // Copy a string to the clipboard with a graceful fallback so the action
  // works on insecure-context dev URLs (no `navigator.clipboard`).
  const copyToClipboard = useCallback(async (url: string) => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
        return true;
      }
    } catch {
      /* fall through to textarea fallback */
    }
    try {
      const ta = document.createElement("textarea");
      ta.value = url;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      return true;
    } catch {
      return false;
    }
  }, []);

  const handleCreateShareLink = useCallback(async () => {
    if (shareBusy) return;
    setShareBusy(true);
    try {
      const res = await apiFetch(`/api/source-check/${data.id}/share-token`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || `Failed to create share link (HTTP ${res.status})`);
        return;
      }
      const body = (await res.json()) as { share_token: string; share_url: string };
      onShareTokenChange(body.share_token);
      const ok = await copyToClipboard(body.share_url);
      if (ok) toast.success("Public link copied");
      else toast.success("Public link created");
    } catch {
      toast.error("Network error — please try again");
    } finally {
      setShareBusy(false);
    }
  }, [data.id, shareBusy, onShareTokenChange, copyToClipboard]);

  const handleCopyShareLink = useCallback(async () => {
    if (!data.share_token) return;
    // Reconstruct the share URL using the current origin so the copied link
    // matches the environment the user is browsing from.
    const url = `${window.location.origin}/check/shared/${data.share_token}`;
    const ok = await copyToClipboard(url);
    if (ok) toast.success("Public link copied");
    else toast.error("Failed to copy link");
  }, [data.share_token, copyToClipboard]);

  const handleRevokeShareLink = useCallback(async () => {
    if (shareBusy) return;
    setShareBusy(true);
    try {
      const res = await apiFetch(`/api/source-check/${data.id}/share-token`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || `Failed to revoke (HTTP ${res.status})`);
        return;
      }
      onShareTokenChange(null);
      toast.success("Public link revoked");
    } catch {
      toast.error("Network error — please try again");
    } finally {
      setShareBusy(false);
    }
  }, [data.id, shareBusy, onShareTokenChange]);

  const handleExport = useCallback(async (format: "json" | "csv") => {
    if (exportBusy) return;
    setExportBusy(format);
    try {
      const res = await apiFetch(
        `/api/source-check/${data.id}/export?format=${format}`,
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || `Export failed (HTTP ${res.status})`);
        return;
      }
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = `artiproof-check-${data.id.slice(0, 8)}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objectUrl);
      toast.success(`Exported as ${format.toUpperCase()}`);
    } catch {
      toast.error("Network error during export");
    } finally {
      setExportBusy(null);
    }
  }, [data.id, exportBusy]);

  return (
    <>
      <PinButton kind="source_check" id={data.id} />

      <Button
        variant="outline"
        size="sm"
        onClick={handleRerun}
        disabled={rerunBusy}
        className="border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-400"
      >
        {rerunBusy ? (
          <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
        ) : (
          <RefreshCw className="mr-1.5 h-4 w-4" />
        )}
        Re-check
      </Button>

      {data.share_token == null ? (
        <Button
          variant="outline"
          size="sm"
          onClick={handleCreateShareLink}
          disabled={shareBusy}
          className="border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-400"
        >
          {shareBusy ? (
            <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
          ) : (
            <Link2 className="mr-1.5 h-4 w-4" />
          )}
          Create share link
        </Button>
      ) : (
        <DropdownMenu>
          <DropdownMenuTrigger
            aria-label="Manage share link"
            className="inline-flex h-9 items-center gap-1.5 rounded-md border border-zinc-300 bg-transparent px-3 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:pointer-events-none disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800"
            disabled={shareBusy}
          >
            {shareBusy ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Link2 className="h-4 w-4" />
            )}
            <span>Share link</span>
            <ChevronDown className="h-3 w-3" aria-hidden="true" />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            className="w-44 border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"
          >
            <DropdownMenuItem
              onClick={handleCopyShareLink}
              className="flex items-center gap-2 text-zinc-700 dark:text-zinc-300"
            >
              <Copy className="h-4 w-4" /> Copy link
            </DropdownMenuItem>
            <DropdownMenuSeparator className="bg-zinc-200 dark:bg-zinc-800" />
            <DropdownMenuItem
              onClick={handleRevokeShareLink}
              className="flex items-center gap-2 text-red-600 dark:text-red-400"
            >
              <Trash2 className="h-4 w-4" /> Revoke link
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}

      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label="Export"
          className="inline-flex h-9 items-center gap-1.5 rounded-md border border-zinc-300 bg-transparent px-3 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:pointer-events-none disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800"
          disabled={exportBusy != null}
        >
          {exportBusy != null ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          <span>Export</span>
          <ChevronDown className="h-3 w-3" aria-hidden="true" />
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          className="w-48 border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"
        >
          <DropdownMenuItem
            onClick={() => handleExport("json")}
            className="flex items-center gap-2 text-zinc-700 dark:text-zinc-300"
          >
            <FileJson className="h-4 w-4" /> Export as JSON
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() => handleExport("csv")}
            className="flex items-center gap-2 text-zinc-700 dark:text-zinc-300"
          >
            <FileSpreadsheet className="h-4 w-4" /> Export as CSV
          </DropdownMenuItem>
          <DropdownMenuSeparator className="bg-zinc-200 dark:bg-zinc-800" />
          <DropdownMenuItem
            onClick={download}
            disabled={reportBusy}
            className="flex items-center gap-2 text-zinc-700 dark:text-zinc-300"
          >
            <Download className="h-4 w-4" /> Generate full PDF report
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={share}
            disabled={reportBusy}
            className="flex items-center gap-2 text-zinc-700 dark:text-zinc-300"
          >
            <Share2 className="h-4 w-4" /> {copied ? "Copied!" : "Share PDF report link"}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Button
        size="sm"
        onClick={download}
        disabled={reportBusy}
        className="bg-brand text-white hover:bg-brand-hover"
      >
        {reportBusy ? (
          <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
        ) : (
          <Download className="mr-1.5 h-4 w-4" />
        )}
        Report
      </Button>

      {reportError && (
        <span className="ml-2 inline-block max-w-xs truncate rounded-md border border-red-500/20 bg-red-500/10 px-2 py-1 text-xs text-red-700 dark:text-red-400">
          {reportError}
        </span>
      )}
    </>
  );
}

// ── Split View (PDF) ──

function SplitView({
  data,
  pdfUrl,
  positionMap,
  pdfViewerRef,
  onFindingClick,
  onShareTokenChange,
}: {
  data: SourceCheckData;
  pdfUrl: string;
  positionMap: PositionMap | null;
  pdfViewerRef: React.RefObject<PdfViewerHandle | null>;
  onFindingClick: (type: "claims" | "ai_detections" | "citations", id: string) => void;
  onShareTokenChange: (token: string | null) => void;
}) {
  const score = data.overall_credibility_score;
  const explanation = score == null ? null : explainCredibility({
    score,
    aiPercent: data.ai_content_percentage,
    misinfoCount: data.misinfo_claims_found,
    citationsTotal: data.citations.length,
    retractedCitations: data.citations.filter((c) => c.is_retracted).length,
    brokenCitations: data.citations.filter((c) => !c.is_accessible && !c.is_retracted).length,
  });

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col gap-4 lg:flex-row">
      {/* Left Panel — Report. Full width on mobile, 40% on lg+ */}
      <div className="w-full shrink-0 overflow-y-auto pr-2 lg:w-[40%]">
        <Breadcrumb
          className="mb-3"
          items={[
            { label: "Dashboard", href: "/dashboard" },
            { label: "Source Checks", href: "/check" },
            { label: "Result" },
          ]}
        />
        <div className="mb-4 flex items-center gap-3">
          <Link
            href="/check"
            aria-label="Back to source checks"
            className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <h1 className="font-display text-xl font-bold text-zinc-900 dark:text-white">Source Check</h1>
        </div>

        {/* Action buttons live above the score for PDF view too */}
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <ActionButtons data={data} onShareTokenChange={onShareTokenChange} />
        </div>

        {/* Score */}
        <Card className="mb-4 border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardContent className="flex flex-col gap-3 py-4">
            <div className="flex items-center gap-4">
              {score == null ? (
                <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full border-3 border-zinc-300 text-center text-[10px] text-zinc-600 dark:border-zinc-700 dark:text-zinc-300">
                  Score unavailable
                </div>
              ) : <div
                role="meter"
                aria-label="Credibility score"
                aria-valuenow={Math.round(score)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuetext={`${Math.round(score)} out of 100`}
                className={`flex h-16 w-16 shrink-0 flex-col items-center justify-center rounded-full border-3 ${scoreColor(score)} ${scoreSolidBorderColor(score)}`}
              >
                <span className="text-xl font-bold">{Math.round(score)}</span>
              </div>}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-zinc-900 dark:text-white">{data.input_title || "PDF Document"}</p>
                <div className="mt-1 flex gap-2">
                  <Badge className="bg-blue-500/20 text-blue-700 text-[10px] dark:text-blue-400">
                    AI: {data.ai_content_percentage == null ? "not assessed" : `${data.ai_content_percentage.toFixed(0)}%`}
                  </Badge>
                  <Badge className="bg-amber-500/20 text-amber-700 text-[10px] dark:text-amber-400">
                    {data.misinfo_claims_found == null ? "Claims not assessed" : `${data.misinfo_claims_found} misinfo`}
                  </Badge>
                </div>
              </div>
            </div>
            {explanation ? <ScoreExplanationCompact explanation={explanation} /> : (
              <p className="text-sm text-zinc-600 dark:text-zinc-300">Required verification evidence is missing. Review the available findings.</p>
            )}
          </CardContent>
        </Card>

        {/* Clickable findings */}
        <FindingsList data={data} positionMap={positionMap} onFindingClick={onFindingClick} />
      </div>

      {/* Right Panel — PDF Viewer. Full height on mobile (stacked below), 60% on lg+ */}
      <div className="min-h-[60vh] flex-1 overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800 lg:min-h-0">
        <Suspense
          fallback={
            <div className="flex h-full items-center justify-center bg-zinc-50 dark:bg-zinc-950">
              <Loader2 className="h-8 w-8 animate-spin text-emerald-700 dark:text-emerald-400" />
            </div>
          }
        >
          <PdfViewer ref={pdfViewerRef} url={pdfUrl} className="h-full" />
        </Suspense>
      </div>
    </div>
  );
}

// ── Findings List (used in split-view left panel) ──

function FindingsList({
  data,
  positionMap,
  onFindingClick,
}: {
  data: SourceCheckData;
  positionMap: PositionMap | null;
  onFindingClick: (type: "claims" | "ai_detections" | "citations", id: string) => void;
}) {
  const hasPositions = !!positionMap;

  return (
    <div className="space-y-3">
      {/* Claims */}
      {data.claims.length > 0 && (
        <div>
          <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-zinc-500">
            <Shield className="h-3 w-3" /> Claims ({data.claims.length})
          </h3>
          {data.claims.map((claim) => {
            const config = VERDICT_CONFIG[claim.verdict] || VERDICT_CONFIG.unverified;
            const Icon = config.icon;
            const clickable = hasPositions && positionMap?.claims?.[claim.id];
            return (
              <button
                key={claim.id}
                type="button"
                onClick={() => clickable && onFindingClick("claims", claim.id)}
                className={`mb-2 w-full rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-left transition dark:border-zinc-800 dark:bg-zinc-800/30 ${clickable ? "cursor-pointer hover:border-brand/40" : ""}`}
              >
                <div className="flex items-center gap-2">
                  <Icon className={`h-4 w-4 shrink-0 ${config.color}`} />
                  <Badge className={`${config.bg} ${config.color} text-[10px]`}>{config.label}</Badge>
                  <span className="text-[10px] text-zinc-500">{(claim.confidence * 100).toFixed(0)}%</span>
                </div>
                <p className="mt-1 text-xs text-zinc-900 dark:text-white line-clamp-2">&ldquo;{claim.claim_text}&rdquo;</p>
                <p className="mt-1 text-[11px] text-zinc-600 dark:text-zinc-400 line-clamp-2">{claim.explanation}</p>
                {claim.true_version && (
                  <p className="mt-1 text-[11px] text-emerald-700 dark:text-emerald-400 line-clamp-1">Correct: {claim.true_version}</p>
                )}
              </button>
            );
          })}
        </div>
      )}

      {/* AI Detections */}
      {data.ai_detections.length > 0 && (
        <div>
          <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-zinc-500">
            <Brain className="h-3 w-3" /> AI Detection ({data.ai_detections.length})
          </h3>
          {data.ai_detections.map((d) => {
            const clickable = hasPositions && positionMap?.ai_detections?.[d.id];
            return (
              <button
                key={d.id}
                type="button"
                onClick={() => clickable && onFindingClick("ai_detections", d.id)}
                className={`mb-2 flex w-full items-start gap-2 rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-left transition dark:border-zinc-800 dark:bg-zinc-800/30 ${clickable ? "cursor-pointer hover:border-brand/40" : ""}`}
              >
                <div className="flex w-12 shrink-0 flex-col items-center">
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
                    <div className={`h-full rounded-full ${aiProbColor(d.ai_probability)}`} style={{ width: `${d.ai_probability * 100}%` }} />
                  </div>
                  <span className="mt-0.5 text-[9px] text-zinc-500">{(d.ai_probability * 100).toFixed(0)}%</span>
                </div>
                <p className="flex-1 text-[11px] text-zinc-600 dark:text-zinc-400 line-clamp-2">{d.paragraph_text}</p>
              </button>
            );
          })}
        </div>
      )}

      {/* Citations */}
      {data.citations.length > 0 && (
        <div>
          <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-zinc-500">
            <BookOpen className="h-3 w-3" /> Citations ({data.citations.length})
          </h3>
          {data.citations.map((cit) => {
            const clickable = hasPositions && positionMap?.citations?.[cit.id];
            return (
              <button
                key={cit.id}
                type="button"
                onClick={() => clickable && onFindingClick("citations", cit.id)}
                className={`mb-2 flex w-full items-start gap-2 rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-left transition dark:border-zinc-800 dark:bg-zinc-800/30 ${clickable ? "cursor-pointer hover:border-yellow-500/40" : ""}`}
              >
                {cit.is_retracted ? (
                  <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-700 dark:text-red-400" />
                ) : !cit.is_accessible ? (
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
                ) : (
                  <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700 dark:text-emerald-400" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs text-zinc-900 dark:text-white">{cit.original_citation}</p>
                  <div className="mt-0.5 flex gap-1">
                    {cit.is_retracted && <Badge className="bg-red-500/20 text-red-700 text-[9px] dark:text-red-400">RETRACTED</Badge>}
                    {!cit.is_accessible && <Badge className="bg-amber-500/20 text-amber-700 text-[9px] dark:text-amber-400">BROKEN</Badge>}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// Re-export shared types so any external importers of this file (none today,
// but historically the page held the canonical `SourceCheckData`) keep working.
export type {
  AIDetection,
  CitationData,
  ClaimData,
  ModelMetadataData,
  ScoreBreakdownData,
};
