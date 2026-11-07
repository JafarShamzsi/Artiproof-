"use client";

import { use, useEffect, useState, useRef, lazy, Suspense } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  ExternalLink,
  Globe,
} from "lucide-react";
import type { PdfViewerHandle } from "@/components/pdf-viewer";

const PdfViewer = lazy(() => import("@/components/pdf-viewer"));

import { apiFetch } from "@/lib/api";
import { useReportActions } from "@/lib/useReportActions";
import { explainCredibility } from "@/lib/scoreExplanation";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import {
  aiProbColor,
  scoreColor,
  scoreSolidBorderColor,
} from "@/lib/colors";
import {
  ScoreExplanationCard,
  ScoreExplanationCompact,
} from "@/components/ui/score-explanation";

// ── Types ──

interface ClaimData {
  id: string;
  claim_text: string;
  verdict: string;
  confidence: number;
  explanation: string;
  true_version: string | null;
  sources: Array<{ name?: string; url?: string }> | null;
  origin_trace: {
    origin_platform?: string;
    first_seen?: string;
    [k: string]: unknown;
  } | null;
  position_in_text: { start: number; end: number } | null;
}

interface AIDetection {
  id: string;
  paragraph_index: number;
  paragraph_text: string;
  ai_probability: number;
  detection_method: string;
}

interface CitationData {
  id: string;
  original_citation: string;
  citation_url: string | null;
  is_accessible: boolean;
  is_retracted: boolean;
  credibility_score: number | null;
  issues: string[] | null;
  suggested_alternative: string | null;
}

interface ScoreBreakdownData {
  base: number;
  deductions: Array<{
    reason: string;
    impact: number;
    detail?: Record<string, unknown>;
  }>;
  warnings?: string[];
  final: number;
  confidence?: number;
  formula_version?: string;
}

interface ModelMetadataData {
  model_provider?: string;
  model_name?: string;
  apis_used?: string[];
  fallback_used?: boolean;
  processing_warnings?: Array<Record<string, unknown>>;
  timestamp?: string;
  formula_version?: string;
  context?: Record<string, unknown>;
}

interface SourceCheckData {
  id: string;
  input_type: string;
  input_content: string;
  input_title: string | null;
  status: string;
  overall_credibility_score: number | null;
  ai_content_percentage: number | null;
  misinfo_claims_found: number | null;
  has_pdf: boolean;
  has_annotated_pdf: boolean;
  created_at: string;
  completed_at: string | null;
  claims: ClaimData[];
  ai_detections: AIDetection[];
  citations: CitationData[];
  score_breakdown?: ScoreBreakdownData | null;
  model_metadata?: ModelMetadataData | null;
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

  useEffect(() => {
    apiFetch(`/api/source-check/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error("Not found");
        return r.json();
      })
      .then((d) => {
        setData(d);
        // Load position map if PDF
        if (d.has_pdf) {
          apiFetch(`/api/source-check/${id}/position-map`)
            .then((r) => r.ok ? r.json() : null)
            .then(setPositionMap)
            .catch(() => {});
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  const handleFindingClick = (type: "claims" | "ai_detections" | "citations", findingId: string) => {
    if (!positionMap || !pdfViewerRef.current) return;
    const mapping = positionMap[type]?.[findingId];
    if (!mapping || !mapping.highlights?.length) return;
    const hl = mapping.highlights[0];
    pdfViewerRef.current.scrollToPosition(hl.page, hl.bbox);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-brand dark:text-brand-fg" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <Link href="/check" className="flex items-center gap-1 text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white">
          <ArrowLeft className="h-4 w-4" /> Back
        </Link>
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardContent className="py-12 text-center">
            <p className="text-red-700 dark:text-red-400">Source check not found.</p>
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
    return <SplitView data={data} pdfUrl={pdfUrl} positionMap={positionMap} pdfViewerRef={pdfViewerRef} onFindingClick={handleFindingClick} />;
  }

  return <FullWidthView data={data} />;
}

// ── Split View (PDF) ──

function SplitView({
  data,
  pdfUrl,
  positionMap,
  pdfViewerRef,
  onFindingClick,
}: {
  data: SourceCheckData;
  pdfUrl: string;
  positionMap: PositionMap | null;
  pdfViewerRef: React.RefObject<PdfViewerHandle | null>;
  onFindingClick: (type: "claims" | "ai_detections" | "citations", id: string) => void;
}) {
  const score = data.overall_credibility_score ?? 0;
  const explanation = explainCredibility({
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

        {/* Score */}
        <Card className="mb-4 border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardContent className="flex flex-col gap-3 py-4">
            <div className="flex items-center gap-4">
              <div
                role="meter"
                aria-label="Credibility score"
                aria-valuenow={Math.round(score)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuetext={`${Math.round(score)} out of 100`}
                className={`flex h-16 w-16 shrink-0 flex-col items-center justify-center rounded-full border-3 ${scoreColor(score)} ${scoreSolidBorderColor(score)}`}
              >
                <span className="text-xl font-bold">{Math.round(score)}</span>
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-zinc-900 dark:text-white">{data.input_title || "PDF Document"}</p>
                <div className="mt-1 flex gap-2">
                  <Badge className="bg-blue-500/20 text-blue-700 text-[10px] dark:text-blue-400">
                    AI: {(data.ai_content_percentage ?? 0).toFixed(0)}%
                  </Badge>
                  <Badge className="bg-amber-500/20 text-amber-700 text-[10px] dark:text-amber-400">
                    {data.misinfo_claims_found ?? 0} misinfo
                  </Badge>
                </div>
              </div>
            </div>
            <ScoreExplanationCompact explanation={explanation} />
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

// ── Full Width View (URL/text — existing layout) ──

function FullWidthView({ data }: { data: SourceCheckData }) {
  const score = data.overall_credibility_score ?? 0;
  const aiPct = data.ai_content_percentage ?? 0;
  const explanation = explainCredibility({
    score,
    aiPercent: aiPct,
    misinfoCount: data.misinfo_claims_found,
    citationsTotal: data.citations.length,
    retractedCitations: data.citations.filter((c) => c.is_retracted).length,
    brokenCitations: data.citations.filter((c) => !c.is_accessible && !c.is_retracted).length,
  });
  const { share, download, busy, copied, error } = useReportActions({
    sourceCheckId: data.id,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/check" className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">Source Check Results</h1>
        </div>
        <div className="flex gap-2">
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

      {data.status !== "completed" && (
        <Card className="border-blue-500/30 bg-blue-500/5">
          <CardContent className="flex items-center gap-3 py-4">
            <Loader2 className="h-5 w-5 animate-spin text-blue-700 dark:text-blue-400" />
            <span className="text-sm text-zinc-700 dark:text-zinc-300">Status: {data.status}</span>
          </CardContent>
        </Card>
      )}

      {/* Score Card */}
      <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
        <CardContent className="py-8">
          <div className="flex flex-col items-center gap-6 md:flex-row">
            <div
              role="meter"
              aria-label="Credibility score"
              aria-valuenow={Math.round(score)}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuetext={`${Math.round(score)} out of 100`}
              className={`flex h-28 w-28 shrink-0 flex-col items-center justify-center rounded-full border-4 ${scoreColor(score)} ${scoreSolidBorderColor(score)}`}
            >
              <span className="text-3xl font-bold">{Math.round(score)}</span>
              <span className="text-xs opacity-70">/ 100</span>
            </div>
            <div className="flex-1 text-center md:text-left">
              <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">{data.input_title || "Credibility Score"}</h2>
              {data.input_type === "url" && (
                <p className="mt-1 flex items-center gap-1 text-sm text-zinc-500">
                  <Globe className="h-3 w-3" /> {data.input_content}
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge className="bg-blue-500/20 text-blue-700 dark:text-blue-400"><Brain className="mr-1 h-3 w-3" /> AI: {aiPct.toFixed(0)}%</Badge>
                <Badge className="bg-amber-500/20 text-amber-700 dark:text-amber-400"><Shield className="mr-1 h-3 w-3" /> {data.misinfo_claims_found ?? 0} misinfo</Badge>
                <Badge className="bg-fg-tertiary/15 text-fg-secondary"><BookOpen className="mr-1 h-3 w-3" /> {data.citations.length} citations</Badge>
              </div>
            </div>
          </div>
          <ScoreExplanationCard explanation={explanation} className="mt-6" />
          {data.score_breakdown && (
            <ScoreBreakdownPanel breakdown={data.score_breakdown} className="mt-6" />
          )}
          {data.model_metadata && (
            <CoverageIndicators metadata={data.model_metadata} className="mt-3" />
          )}
        </CardContent>
      </Card>

      {/* Claims */}
      {data.claims.length > 0 && (
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400"><Shield className="h-4 w-4" /> Claims ({data.claims.length})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {data.claims.map((claim) => {
              const config = VERDICT_CONFIG[claim.verdict] || VERDICT_CONFIG.unverified;
              const Icon = config.icon;
              return (
                <div key={claim.id} className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-800/30">
                  <div className="flex items-start gap-3">
                    <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${config.color}`} />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <Badge className={`${config.bg} ${config.color}`}>{config.label}</Badge>
                        <span className="text-xs text-zinc-500">{(claim.confidence * 100).toFixed(0)}%</span>
                      </div>
                      <p className="mt-2 text-sm text-zinc-900 dark:text-white">&ldquo;{claim.claim_text}&rdquo;</p>
                      <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">{claim.explanation}</p>
                      {claim.true_version && (
                        <div className="mt-2 rounded border border-emerald-500/20 bg-emerald-500/5 p-2">
                          <p className="text-xs font-medium text-emerald-700 dark:text-emerald-400">Correct version:</p>
                          <p className="text-sm text-zinc-700 dark:text-zinc-300">{claim.true_version}</p>
                        </div>
                      )}
                      {claim.origin_trace && (
                        <div className="mt-2 rounded border border-amber-500/20 bg-amber-500/5 p-2">
                          <p className="text-xs font-medium text-amber-700 dark:text-amber-400">Origin: {claim.origin_trace.origin_platform} ({claim.origin_trace.first_seen})</p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* AI Detection */}
      {data.ai_detections.length > 0 && (
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400"><Brain className="h-4 w-4" /> AI Detection</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.ai_detections.map((d) => (
              <div key={d.id} className="flex items-start gap-3">
                <div className="flex w-16 shrink-0 flex-col items-center">
                  <div className="h-3 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
                    <div className={`h-full rounded-full ${aiProbColor(d.ai_probability)}`} style={{ width: `${d.ai_probability * 100}%` }} />
                  </div>
                  <span className="mt-1 text-[10px] text-zinc-500">{(d.ai_probability * 100).toFixed(0)}%</span>
                </div>
                <p className="flex-1 text-sm text-zinc-600 dark:text-zinc-400 line-clamp-2">{d.paragraph_text}</p>
              </div>
            ))}
            <p className="border-t border-zinc-200 pt-3 text-[11px] leading-relaxed text-zinc-500 dark:border-zinc-800">
              AI detection is probabilistic and should be treated as one signal
              among many — not as proof of authorship.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Citations */}
      {data.citations.length > 0 && (
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400"><BookOpen className="h-4 w-4" /> Citations ({data.citations.length})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.citations.map((cit) => (
              <div key={cit.id} className="flex items-start gap-3 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-800/30">
                {cit.is_retracted ? (
                  <>
                    <XCircle aria-hidden="true" className="h-4 w-4 text-red-700 dark:text-red-400" />
                    <span className="sr-only">Retracted citation:</span>
                  </>
                ) : !cit.is_accessible ? (
                  <>
                    <AlertTriangle aria-hidden="true" className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                    <span className="sr-only">Inaccessible citation:</span>
                  </>
                ) : (
                  <>
                    <CheckCircle aria-hidden="true" className="h-4 w-4 text-emerald-700 dark:text-emerald-400" />
                    <span className="sr-only">Verified citation:</span>
                  </>
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-zinc-900 dark:text-white">{cit.original_citation}</p>
                  {cit.citation_url && (
                    <a href={cit.citation_url} target="_blank" rel="noopener noreferrer" className="mt-0.5 flex items-center gap-1 text-xs text-blue-700 hover:underline dark:text-blue-400">
                      {cit.citation_url.substring(0, 60)}... <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                  <div className="mt-1 flex flex-wrap gap-1">
                    {cit.is_retracted && <Badge className="bg-red-500/20 text-red-700 text-[10px] dark:text-red-400">RETRACTED</Badge>}
                    {!cit.is_accessible && <Badge className="bg-amber-500/20 text-amber-700 text-[10px] dark:text-amber-400">INACCESSIBLE</Badge>}
                  </div>
                  {cit.issues?.map((issue: string, i: number) => (
                    <p key={i} className="mt-0.5 text-xs text-amber-700/90 dark:text-amber-400/80">- {issue}</p>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ─── Score breakdown / coverage helpers ───

function ScoreBreakdownPanel({
  breakdown,
  className = "",
}: {
  breakdown: ScoreBreakdownData;
  className?: string;
}) {
  if (!breakdown.deductions || breakdown.deductions.length === 0) {
    return null;
  }
  return (
    <div className={`rounded-lg border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950/40 ${className}`}>
      <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
        Score breakdown
      </h4>
      <div className="mt-3 space-y-1.5">
        <div className="flex justify-between text-xs text-zinc-500">
          <span>Starting score</span>
          <span>{breakdown.base.toFixed(0)}</span>
        </div>
        {breakdown.deductions.map((d, i) => (
          <div key={i} className="flex justify-between text-xs">
            <span className="text-zinc-700 dark:text-zinc-300">
              {d.reason.replace(/_/g, " ")}
            </span>
            <span className="text-red-700 dark:text-red-400">
              {d.impact > 0 ? "+" : ""}
              {d.impact.toFixed(1)}
            </span>
          </div>
        ))}
        <div className="flex justify-between border-t border-zinc-200 pt-1.5 text-xs font-medium dark:border-zinc-800">
          <span className="text-zinc-900 dark:text-white">Final</span>
          <span className="text-zinc-900 dark:text-white">{breakdown.final.toFixed(1)}</span>
        </div>
        {typeof breakdown.confidence === "number" && (
          <div className="flex justify-between pt-1 text-xs">
            <span className="text-zinc-500">Confidence</span>
            <span className="text-zinc-700 dark:text-zinc-300">
              {Math.round(breakdown.confidence * 100)}%
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function CoverageIndicators({
  metadata,
  className = "",
}: {
  metadata: ModelMetadataData;
  className?: string;
}) {
  const ctx = metadata.context || {};
  const truncated = Boolean(
    metadata.processing_warnings?.some(
      (w) => w["type"] === "text_truncated",
    ),
  );
  const paragraphsCapped = Boolean(
    metadata.processing_warnings?.some(
      (w) => w["type"] === "paragraphs_capped",
    ),
  );
  const claimsExtracted = typeof ctx.claims_extracted === "number" ? ctx.claims_extracted : null;
  const paragraphs = typeof ctx.paragraphs_analyzed === "number" ? ctx.paragraphs_analyzed : null;
  const textLength = typeof ctx.text_length === "number" ? ctx.text_length : null;

  // Hide entirely if we have nothing useful to show
  if (!truncated && !paragraphsCapped && claimsExtracted == null && paragraphs == null) {
    return null;
  }

  return (
    <div className={`flex flex-wrap gap-2 ${className}`}>
      {truncated && textLength != null && (
        <span className="rounded bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-700 dark:text-amber-300">
          First 15,000 of {textLength.toLocaleString()} chars analyzed
        </span>
      )}
      {paragraphsCapped && (
        <span className="rounded bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-700 dark:text-amber-300">
          AI detection capped at 20 paragraphs
        </span>
      )}
      {claimsExtracted != null && (
        <span className="rounded bg-zinc-100 px-2 py-0.5 text-[10px] text-zinc-700 dark:bg-zinc-800 dark:text-zinc-400">
          {claimsExtracted} claim{claimsExtracted === 1 ? "" : "s"} extracted
        </span>
      )}
      {paragraphs != null && paragraphs > 0 && (
        <span className="rounded bg-zinc-100 px-2 py-0.5 text-[10px] text-zinc-700 dark:bg-zinc-800 dark:text-zinc-400">
          {paragraphs} paragraph{paragraphs === 1 ? "" : "s"} analyzed
        </span>
      )}
      {metadata.fallback_used && (
        <span className="rounded bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-700 dark:text-amber-300">
          Heuristic fallback used
        </span>
      )}
    </div>
  );
}
