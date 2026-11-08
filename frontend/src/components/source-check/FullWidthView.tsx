"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Shield,
  Brain,
  BookOpen,
  CheckCircle,
  XCircle,
  AlertTriangle,
  HelpCircle,
  Loader2,
  ArrowLeft,
  ExternalLink,
  Globe,
} from "lucide-react";

import { explainCredibility } from "@/lib/scoreExplanation";
import {
  aiProbColor,
  scoreColor,
  scoreSolidBorderColor,
} from "@/lib/colors";
import {
  ScoreExplanationCard,
} from "@/components/ui/score-explanation";

// ── Types — shared across the authed and public source-check views. ──

export interface ClaimData {
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

export interface AIDetection {
  id: string;
  paragraph_index: number;
  paragraph_text: string;
  ai_probability: number;
  detection_method: string;
}

export interface CitationData {
  id: string;
  original_citation: string;
  citation_url: string | null;
  is_accessible: boolean;
  is_retracted: boolean;
  credibility_score: number | null;
  issues: string[] | null;
  suggested_alternative: string | null;
}

export interface ScoreBreakdownData {
  base: number;
  deductions: Array<{
    reason: string;
    impact: number;
    detail?: Record<string, unknown>;
  }>;
  warnings?: string[];
  final: number | null;
  confidence?: number;
  formula_version?: string;
  assessment_status?: "available" | "partial" | "unavailable";
}

export interface ModelMetadataData {
  model_provider?: string;
  model_name?: string;
  apis_used?: string[];
  fallback_used?: boolean;
  processing_warnings?: Array<Record<string, unknown>>;
  timestamp?: string;
  formula_version?: string;
  context?: Record<string, unknown>;
}

/**
 * Shape consumed by the full-width view. Both
 * `SourceCheckResponse` and `SharedSourceCheckResponse` from the backend
 * conform to this — `input_content` is optional because the public shared
 * view redacts it for url-type checks, and `model_metadata` is omitted there.
 */
export interface CoverageNoteData {
  kind: string;
  severity: "info" | "warning";
  headline: string;
  detail: string;
}

export interface CoverageSummaryData {
  notes: CoverageNoteData[];
  claims_analyzed: number | null;
  claims_extracted: number | null;
  paragraphs_analyzed: number | null;
  paragraphs_total: number | null;
  text_chars_analyzed: number | null;
  text_chars_total: number | null;
}

export interface FullWidthSourceCheckData {
  id: string;
  input_type: string;
  input_content?: string;
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
  /** Backend-computed coverage caveats. Present in current API responses;
   * older clients/snapshots may omit it, so the CoverageIndicators
   * component still derives a fallback view from model_metadata. */
  coverage?: CoverageSummaryData | null;
}

// Verdict text shades use the deeper -800/-300 pair so the badge text
// clears WCAG AA contrast over the /20 tint backgrounds in both modes.
const VERDICT_CONFIG: Record<
  string,
  { icon: typeof CheckCircle; color: string; bg: string; label: string }
> = {
  true: { icon: CheckCircle, color: "text-emerald-800 dark:text-emerald-300", bg: "bg-emerald-500/20", label: "True" },
  false: { icon: XCircle, color: "text-red-800 dark:text-red-300", bg: "bg-red-500/20", label: "False" },
  misleading: { icon: AlertTriangle, color: "text-amber-800 dark:text-amber-300", bg: "bg-amber-500/20", label: "Misleading" },
  partially_true: { icon: AlertTriangle, color: "text-yellow-800 dark:text-yellow-300", bg: "bg-yellow-500/20", label: "Partially True" },
  unverified: { icon: HelpCircle, color: "text-zinc-700 dark:text-zinc-300", bg: "bg-zinc-500/20", label: "Unverified" },
};

interface FullWidthViewProps {
  data: FullWidthSourceCheckData;
  /**
   * When true, the back-link header bar is rendered with no action buttons
   * and the page heading is "Shared Source Check". Used by the public
   * `/check/shared/[token]` route. Defaults to false (authed view).
   */
  readOnly?: boolean;
  /**
   * Authed-view action buttons (Pin, Re-check, Share link, Export, Report).
   * Ignored when `readOnly` is true. Pass a single fragment / element row.
   */
  actionsSlot?: ReactNode;
  /**
   * Optional override for the back-link href; defaults to `/check`. Used
   * by the public shared view to point at the marketing landing page.
   */
  backHref?: string;
  /** Optional banner rendered below the header (e.g. "Read-only shared view"). */
  banner?: ReactNode;
}

/**
 * Full-width source-check report — used for URL/text checks (not PDFs).
 * Lifts all visual content out of `(dashboard)/check/[id]/page.tsx` so both
 * the authed detail view and the public `/check/shared/[token]` view can
 * render the same body.
 */
export function FullWidthView({
  data,
  readOnly = false,
  actionsSlot,
  backHref = "/check",
  banner,
}: FullWidthViewProps) {
  const score = data.overall_credibility_score;
  const aiPct = data.ai_content_percentage;
  const explanation = score == null ? null : explainCredibility({
    score,
    aiPercent: aiPct ?? 0,
    misinfoCount: data.misinfo_claims_found,
    citationsTotal: data.citations.length,
    retractedCitations: data.citations.filter((c) => c.is_retracted).length,
    brokenCitations: data.citations.filter((c) => !c.is_accessible && !c.is_retracted).length,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href={backHref}
            aria-label="Back"
            className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <h1 className="truncate text-2xl font-bold text-zinc-900 dark:text-white">
            {readOnly ? "Shared Source Check" : "Source Check Results"}
          </h1>
        </div>
        {!readOnly && actionsSlot && (
          <div className="flex flex-wrap items-center gap-2">{actionsSlot}</div>
        )}
      </div>

      {banner}

      {data.status !== "completed" && (
        <Card className="border-blue-500/30 bg-blue-500/5">
          <CardContent className="flex items-center gap-3 py-4">
            {data.status === "failed" ? (
              <AlertTriangle className="h-5 w-5 text-amber-700 dark:text-amber-400" />
            ) : (
              <Loader2 className="h-5 w-5 animate-spin text-blue-700 dark:text-blue-400" />
            )}
            <span className="text-sm text-zinc-700 dark:text-zinc-300">Status: {data.status}</span>
          </CardContent>
        </Card>
      )}

      {/* Score Card */}
      <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
        <CardContent className="py-8">
          <div className="flex flex-col items-center gap-6 md:flex-row">
            {score == null ? (
              <div className="flex h-28 w-28 shrink-0 items-center justify-center rounded-full border-4 border-zinc-300 px-2 text-center text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-300">
                Score unavailable
              </div>
            ) : <div
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
            </div>}
            <div className="flex-1 text-center md:text-left">
              <h2 className="text-xl font-semibold text-zinc-900 dark:text-white">
                {data.input_title || "Credibility Score"}
              </h2>
              {data.input_type === "url" && data.input_content && (
                <p className="mt-1 flex items-center gap-1 text-sm text-zinc-500">
                  <Globe className="h-3 w-3" /> {data.input_content}
                </p>
              )}
              {/* Score summary badges — text shades deepened in light mode
                  (text-{color}-800) to clear WCAG AA 4.5:1 over the
                  /20 tinted backgrounds. Dark mode keeps its existing
                  text-{color}-300 which already passes. */}
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge className="bg-blue-500/20 text-blue-800 dark:text-blue-300">
                  <Brain className="mr-1 h-3 w-3" /> AI: {aiPct == null ? "not assessed" : `${aiPct.toFixed(0)}%`}
                </Badge>
                <Badge className="bg-amber-500/20 text-amber-800 dark:text-amber-300">
                  <Shield className="mr-1 h-3 w-3" /> {data.misinfo_claims_found == null ? "Claims not assessed" : `${data.misinfo_claims_found} misinfo`}
                </Badge>
                <Badge className="bg-zinc-200 text-zinc-700 dark:bg-zinc-700/40 dark:text-zinc-200">
                  <BookOpen className="mr-1 h-3 w-3" /> {data.citations.length} citations
                </Badge>
              </div>
            </div>
          </div>
          {data.score_breakdown?.assessment_status === "partial" && <p className="mt-4 text-sm text-amber-800 dark:text-amber-300">Partial assessment: some claims or references were not checked. The score summarizes recorded findings, not overall accuracy.</p>}
          {explanation ? (
            <ScoreExplanationCard explanation={explanation} className="mt-6" />
          ) : (
            <p className="mt-6 text-sm text-zinc-600 dark:text-zinc-300">
              A credibility score is unavailable. Missing analysis is not evidence that the source is accurate or inaccurate. Review the status and coverage details below.
            </p>
          )}
          {data.score_breakdown && (
            <ScoreBreakdownPanel breakdown={data.score_breakdown} className="mt-6" />
          )}
          {/* Coverage caveats — surfaced on BOTH authed and read-only views;
              an institutional buyer reading a shared report has the same
              right to know which parts of the source were sampled vs
              skipped. Prefer the backend-computed summary; fall back to
              the legacy model_metadata derivation. */}
          {(data.coverage || data.model_metadata) && (
            <CoverageIndicators
              coverage={data.coverage ?? null}
              metadata={data.model_metadata ?? null}
              className="mt-3"
            />
          )}
        </CardContent>
      </Card>

      {/* Claims */}
      {data.claims.length > 0 && (
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
              <Shield className="h-4 w-4" /> Claims ({data.claims.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {data.claims.map((claim) => {
              const config = VERDICT_CONFIG[claim.verdict] || VERDICT_CONFIG.unverified;
              const Icon = config.icon;
              return (
                <div
                  key={claim.id}
                  className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-800/30"
                >
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
                          <p className="text-xs font-medium text-amber-700 dark:text-amber-400">
                            Origin: {claim.origin_trace.origin_platform} ({claim.origin_trace.first_seen})
                          </p>
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
            <CardTitle className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
              <Brain className="h-4 w-4" /> AI Detection
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.ai_detections.map((d) => (
              <div key={d.id} className="flex items-start gap-3">
                <div className="flex w-16 shrink-0 flex-col items-center">
                  <div className="h-3 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
                    <div
                      className={`h-full rounded-full ${aiProbColor(d.ai_probability)}`}
                      style={{ width: `${d.ai_probability * 100}%` }}
                    />
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
            <CardTitle className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
              <BookOpen className="h-4 w-4" /> Citations ({data.citations.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.citations.map((cit) => (
              <div
                key={cit.id}
                className="flex items-start gap-3 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-800/30"
              >
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
                    <a
                      href={cit.citation_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-0.5 flex items-center gap-1 text-xs text-blue-700 hover:underline dark:text-blue-400"
                    >
                      {cit.citation_url.length > 60
                        ? `${cit.citation_url.substring(0, 60)}…`
                        : cit.citation_url}{" "}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                  <div className="mt-1 flex flex-wrap gap-1">
                    {cit.is_retracted && (
                      <Badge className="bg-red-500/20 text-red-700 text-[10px] dark:text-red-400">RETRACTED</Badge>
                    )}
                    {!cit.is_accessible && (
                      <Badge className="bg-amber-500/20 text-amber-700 text-[10px] dark:text-amber-400">INACCESSIBLE</Badge>
                    )}
                  </div>
                  {cit.issues?.map((issue: string, i: number) => (
                    <p key={i} className="mt-0.5 text-xs text-amber-700/90 dark:text-amber-400/80">
                      - {issue}
                    </p>
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

// ─── Score breakdown / coverage helpers (also used by FullWidthView) ───

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
          <span className="text-zinc-900 dark:text-white">{breakdown.final == null ? "Unavailable" : breakdown.final.toFixed(1)}</span>
        </div>
        {typeof breakdown.confidence === "number" && (
          <div className="flex justify-between pt-1 text-xs">
            <span className="text-zinc-500">Evidence indicator (not calibrated accuracy)</span>
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
  coverage,
  metadata,
  className = "",
}: {
  coverage: CoverageSummaryData | null;
  metadata: ModelMetadataData | null;
  className?: string;
}) {
  // Prefer the backend-computed summary when present. It tracks the actual
  // truncation constants and warning types, so we don't drift when the
  // pipeline limits change.
  if (coverage) {
    const warnings = coverage.notes.filter((n) => n.severity === "warning");
    const info = coverage.notes.filter((n) => n.severity === "info");
    const hasFigures =
      coverage.claims_analyzed != null ||
      coverage.paragraphs_analyzed != null ||
      coverage.text_chars_analyzed != null;
    if (warnings.length === 0 && info.length === 0 && !hasFigures) return null;

    return (
      <div className={`space-y-2 ${className}`}>
        {warnings.length > 0 && (
          <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3">
            <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-300">
              Coverage caveats
            </div>
            <ul className="space-y-1.5">
              {warnings.map((note) => (
                <li
                  key={`${note.kind}-${note.headline}`}
                  className="text-xs leading-relaxed text-amber-900 dark:text-amber-100"
                >
                  <span className="font-medium">{note.headline}</span>
                  <span className="text-amber-800/80 dark:text-amber-200/80">
                    {" "}
                    — {note.detail}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {(info.length > 0 || hasFigures) && (
          <div className="flex flex-wrap gap-2">
            {info.map((note) => (
              <span
                key={note.kind}
                className="rounded bg-zinc-100 px-2 py-0.5 text-[10px] text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                title={note.detail}
              >
                {note.headline}
              </span>
            ))}
            {coverage.claims_analyzed != null && warnings.every((w) => w.kind !== "claims_capped") && (
              <span className="rounded bg-zinc-100 px-2 py-0.5 text-[10px] text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                {coverage.claims_analyzed} claim
                {coverage.claims_analyzed === 1 ? "" : "s"} verified
              </span>
            )}
            {coverage.paragraphs_analyzed != null &&
              warnings.every((w) => w.kind !== "paragraphs_capped") && (
                <span className="rounded bg-zinc-100 px-2 py-0.5 text-[10px] text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                  {coverage.paragraphs_analyzed} paragraph
                  {coverage.paragraphs_analyzed === 1 ? "" : "s"} analyzed
                </span>
              )}
          </div>
        )}
      </div>
    );
  }

  // Legacy fallback: derive a minimal pill view from model_metadata directly
  // for responses that pre-date the structured `coverage` field.
  if (!metadata) return null;
  const ctx = metadata.context || {};
  const truncated = Boolean(
    metadata.processing_warnings?.some((w) => w["type"] === "text_truncated"),
  );
  const paragraphsCapped = Boolean(
    metadata.processing_warnings?.some((w) => w["type"] === "paragraphs_capped"),
  );
  const claimsExtracted =
    typeof ctx.claims_extracted === "number" ? ctx.claims_extracted : null;
  const paragraphs =
    typeof ctx.paragraphs_analyzed === "number" ? ctx.paragraphs_analyzed : null;
  const textLength = typeof ctx.text_length === "number" ? ctx.text_length : null;

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
