"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  AlertTriangle,
  ArrowLeft,
  Brain,
  BookOpen,
  Loader2,
  Shield,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { explainCredibility } from "@/lib/scoreExplanation";
import {
  ScoreExplanationCompact,
} from "@/components/ui/score-explanation";
import {
  scoreColor,
  scoreSolidBorderColor,
} from "@/lib/colors";
import type { SourceCheck } from "@/types/api";

export default function CompareSourceChecksPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-brand dark:text-brand-fg" />
        </div>
      }
    >
      <CompareInner />
    </Suspense>
  );
}

function CompareInner() {
  const searchParams = useSearchParams();
  const idA = searchParams.get("a");
  const idB = searchParams.get("b");

  // Derived states default to "loading only when there's an id to load":
  // when the URL is missing a/b we render the missing-id error directly
  // without ever entering a loading state, which keeps the effect free of
  // the `set-state-in-effect` cascade lint rule.
  const [dataA, setDataA] = useState<SourceCheck | null>(null);
  const [dataB, setDataB] = useState<SourceCheck | null>(null);
  const [errorA, setErrorA] = useState<string | null>(null);
  const [errorB, setErrorB] = useState<string | null>(null);
  const [loadingA, setLoadingA] = useState<boolean>(!!idA);
  const [loadingB, setLoadingB] = useState<boolean>(!!idB);

  useEffect(() => {
    const ctl = new AbortController();
    if (!idA) return undefined;
    apiFetch(`/api/source-check/${idA}`, { signal: ctl.signal })
      .then(async (r) => {
        if (!r.ok) throw new Error(r.status === 404 ? "Not found" : `HTTP ${r.status}`);
        return r.json();
      })
      .then(setDataA)
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setErrorA(e instanceof Error ? e.message : "Failed to load");
      })
      .finally(() => setLoadingA(false));
    return () => ctl.abort();
  }, [idA]);

  useEffect(() => {
    const ctl = new AbortController();
    if (!idB) return undefined;
    apiFetch(`/api/source-check/${idB}`, { signal: ctl.signal })
      .then(async (r) => {
        if (!r.ok) throw new Error(r.status === 404 ? "Not found" : `HTTP ${r.status}`);
        return r.json();
      })
      .then(setDataB)
      .catch((e) => {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setErrorB(e instanceof Error ? e.message : "Failed to load");
      })
      .finally(() => setLoadingB(false));
    return () => ctl.abort();
  }, [idB]);

  // Surface the "missing query param" error as a derived value rather than
  // a state setter inside an effect. Initial loading flags above default
  // to false when the param is absent, so the panel renders the error path.
  const effectiveErrorA = errorA ?? (!idA ? "Missing check id (a)" : null);
  const effectiveErrorB = errorB ?? (!idB ? "Missing check id (b)" : null);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/check"
          aria-label="Back to source checks"
          className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <h1 className="font-display text-2xl font-bold text-zinc-900 dark:text-white">
          Compare Source Checks
        </h1>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ComparePanel
          label="A"
          id={idA}
          data={dataA}
          loading={loadingA}
          error={effectiveErrorA}
        />
        <ComparePanel
          label="B"
          id={idB}
          data={dataB}
          loading={loadingB}
          error={effectiveErrorB}
        />
      </div>
    </div>
  );
}

function ComparePanel({
  label,
  id,
  data,
  loading,
  error,
}: {
  label: string;
  id: string | null;
  data: SourceCheck | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) {
    return (
      <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
        <CardContent className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-brand dark:text-brand-fg" />
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="text-sm text-zinc-600 dark:text-zinc-400">
            Check {label}
          </CardTitle>
        </CardHeader>
        <CardContent className="py-8 text-center text-sm text-red-700 dark:text-red-400">
          <AlertTriangle className="mx-auto mb-2 h-6 w-6" />
          {error || "Could not load check"}
          {id && <p className="mt-1 text-xs text-zinc-500">id: {id}</p>}
        </CardContent>
      </Card>
    );
  }

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

  const trueClaims = data.claims.filter((c) => c.verdict === "true").length;
  const falseClaims = data.claims.filter(
    (c) => c.verdict === "false" || c.verdict === "misleading",
  ).length;
  const retracted = data.citations.filter((c) => c.is_retracted).length;
  const broken = data.citations.filter((c) => !c.is_accessible && !c.is_retracted).length;

  return (
    <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <CardTitle className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
              <Badge className="bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                {label}
              </Badge>
              <Link
                href={`/check/${data.id}`}
                className="truncate text-xs text-brand hover:underline dark:text-brand-fg"
              >
                {data.input_title || data.input_type.toUpperCase()}
              </Link>
            </CardTitle>
            <p className="mt-1 truncate text-xs text-zinc-500">
              {new Date(data.created_at).toLocaleString()}
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Score gauge */}
        <div className="flex items-center gap-4">
          {score == null ? (
            <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full border-4 border-zinc-300 text-center text-xs text-zinc-600 dark:border-zinc-700 dark:text-zinc-300">
              Score unavailable
            </div>
          ) : <div
            role="meter"
            aria-label={`Credibility score for check ${label}`}
            aria-valuenow={Math.round(score)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuetext={`${Math.round(score)} out of 100`}
            className={`flex h-20 w-20 shrink-0 flex-col items-center justify-center rounded-full border-4 ${scoreColor(score)} ${scoreSolidBorderColor(score)}`}
          >
            <span className="text-2xl font-bold">{Math.round(score)}</span>
            <span className="text-[10px] opacity-70">/ 100</span>
          </div>}
          <div className="flex-1">
            {explanation ? <ScoreExplanationCompact explanation={explanation} /> : (
              <p className="text-sm text-zinc-600 dark:text-zinc-300">Required verification evidence is missing. Review the available findings.</p>
            )}
          </div>
        </div>

        {/* AI percentage */}
        <div>
          <div className="mb-1 flex items-center justify-between text-xs">
            <span className="flex items-center gap-1.5 text-zinc-600 dark:text-zinc-400">
              <Brain className="h-3.5 w-3.5" /> AI content
            </span>
            <span className="font-medium tabular-nums text-zinc-900 dark:text-white">
              {aiPct == null ? "Not assessed" : `${aiPct.toFixed(0)}%`}
            </span>
          </div>
          {aiPct != null && <div
            role="progressbar"
            aria-label="AI content percentage"
            aria-valuenow={Math.round(aiPct)}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-2 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800"
          >
            <div
              className={
                "h-full rounded-full transition-all " +
                (aiPct >= 70 ? "bg-red-500" : aiPct >= 40 ? "bg-amber-500" : "bg-emerald-500")
              }
              style={{ width: `${Math.min(100, aiPct)}%` }}
            />
          </div>}
        </div>

        {/* Score breakdown */}
        {data.score_breakdown && data.score_breakdown.deductions.length > 0 && (
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs dark:border-zinc-800 dark:bg-zinc-950/40">
            <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
              Score breakdown
            </h4>
            <div className="space-y-1">
              <div className="flex justify-between text-zinc-500">
                <span>Starting score</span>
                <span>{data.score_breakdown.base.toFixed(0)}</span>
              </div>
              {data.score_breakdown.deductions.map((d, i) => (
                <div key={i} className="flex justify-between">
                  <span className="text-zinc-700 dark:text-zinc-300">
                    {d.reason.replace(/_/g, " ")}
                  </span>
                  <span className="text-red-700 dark:text-red-400 tabular-nums">
                    {d.impact > 0 ? "+" : ""}
                    {d.impact.toFixed(1)}
                  </span>
                </div>
              ))}
              <div className="flex justify-between border-t border-zinc-200 pt-1 font-medium dark:border-zinc-800">
                <span className="text-zinc-900 dark:text-white">Final</span>
                <span className="text-zinc-900 dark:text-white">
                  {data.score_breakdown.final == null ? "Unavailable" : data.score_breakdown.final.toFixed(1)}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Claim summary */}
        <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-950/40">
          <h4 className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
            <Shield className="h-3 w-3" /> Claims ({data.claims.length})
          </h4>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="rounded bg-emerald-500/10 px-2 py-1.5 text-center">
              <div className="font-bold text-emerald-700 dark:text-emerald-400">
                {trueClaims}
              </div>
              <div className="text-[10px] text-zinc-500">True</div>
            </div>
            <div className="rounded bg-red-500/10 px-2 py-1.5 text-center">
              <div className="font-bold text-red-700 dark:text-red-400">{falseClaims}</div>
              <div className="text-[10px] text-zinc-500">False / misleading</div>
            </div>
            <div className="rounded bg-amber-500/10 px-2 py-1.5 text-center">
              <div className="font-bold text-amber-700 dark:text-amber-400">
                {data.misinfo_claims_found ?? 0}
              </div>
              <div className="text-[10px] text-zinc-500">Misinfo flagged</div>
            </div>
          </div>
        </div>

        {/* Citations summary */}
        <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-950/40">
          <h4 className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
            <BookOpen className="h-3 w-3" /> Citations ({data.citations.length})
          </h4>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="rounded bg-emerald-500/10 px-2 py-1.5 text-center">
              <div className="font-bold text-emerald-700 dark:text-emerald-400">
                {data.citations.length - retracted - broken}
              </div>
              <div className="text-[10px] text-zinc-500">Verified</div>
            </div>
            <div className="rounded bg-amber-500/10 px-2 py-1.5 text-center">
              <div className="font-bold text-amber-700 dark:text-amber-400">{broken}</div>
              <div className="text-[10px] text-zinc-500">Broken</div>
            </div>
            <div className="rounded bg-red-500/10 px-2 py-1.5 text-center">
              <div className="font-bold text-red-700 dark:text-red-400">{retracted}</div>
              <div className="text-[10px] text-zinc-500">Retracted</div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
