"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  Loader2,
  Users,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { explainIntegrity } from "@/lib/scoreExplanation";
import { ScoreExplanationCompact } from "@/components/ui/score-explanation";
import { ResearcherScore, ResearcherCoverage } from "@/components/researcher/assessment";
import type { ResearcherProfile } from "@/types/api";

export default function CompareResearchersPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-accent-amber" />
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
  // without ever entering a loading state.
  const [dataA, setDataA] = useState<ResearcherProfile | null>(null);
  const [dataB, setDataB] = useState<ResearcherProfile | null>(null);
  const [errorA, setErrorA] = useState<string | null>(null);
  const [errorB, setErrorB] = useState<string | null>(null);
  const [loadingA, setLoadingA] = useState<boolean>(!!idA);
  const [loadingB, setLoadingB] = useState<boolean>(!!idB);

  useEffect(() => {
    const ctl = new AbortController();
    if (!idA) return undefined;
    apiFetch(`/api/researcher/${idA}`, { signal: ctl.signal })
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
    apiFetch(`/api/researcher/${idB}`, { signal: ctl.signal })
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

  const effectiveErrorA = errorA ?? (!idA ? "Missing researcher id (a)" : null);
  const effectiveErrorB = errorB ?? (!idB ? "Missing researcher id (b)" : null);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/researcher"
          aria-label="Back to researchers"
          className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <h1 className="font-display text-2xl font-bold text-zinc-900 dark:text-white">
          Compare Researchers
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
  data: ResearcherProfile | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) {
    return (
      <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
        <CardContent className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-accent-amber" />
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="text-sm text-zinc-600 dark:text-zinc-400">
            Researcher {label}
          </CardTitle>
        </CardHeader>
        <CardContent className="py-8 text-center text-sm text-red-700 dark:text-red-400">
          <AlertTriangle className="mx-auto mb-2 h-6 w-6" />
          {error || "Could not load profile"}
          {id && <p className="mt-1 text-xs text-zinc-500">id: {id}</p>}
        </CardContent>
      </Card>
    );
  }

  const score = data.integrity_score;
  const ringFlags = data.citation_ring_flags || null;
  const flags = ringFlags?.flags ?? [];
  const explanation = score == null ? null : explainIntegrity({
    score,
    selfCitationRate: data.self_citation_rate,
    topicRelevanceScore: data.topic_relevance_score,
    flagCount: flags.length,
    publicationsCount: data.publications.length,
  });

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
                href={`/researcher/${data.id}`}
                className="truncate text-xs text-accent-amber hover:underline"
              >
                {data.researcher_name}
              </Link>
            </CardTitle>
            <p className="mt-1 truncate text-xs text-zinc-500">
              {data.institution || "Unknown institution"}
              {data.orcid && (
                <>
                  {" — ORCID: "}
                  <span className="font-mono">{data.orcid}</span>
                </>
              )}
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Integrity score gauge */}
        <div className="flex items-center gap-4">
          <ResearcherScore score={score} label={`Integrity score for researcher ${label}`} />
          <div className="flex-1">
            {explanation ? <ScoreExplanationCompact explanation={explanation} /> : <p className="text-xs text-zinc-600 dark:text-zinc-300">Assessment unavailable; required evidence is missing or a step failed.</p>}
          </div>
        </div>

        <ResearcherCoverage findings={ringFlags} assessment={data.integrity_breakdown} />

        {/* h-index + citations: official vs adjusted, four numbers per side */}
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-950/40">
            <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
              Official
            </h4>
            <div className="space-y-1 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-zinc-600 dark:text-zinc-400">h-index</span>
                <span className="font-bold tabular-nums text-zinc-900 dark:text-white">
                  {data.official_h_index ?? "—"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-600 dark:text-zinc-400">Citations</span>
                <span className="font-bold tabular-nums text-zinc-900 dark:text-white">
                  {data.official_citation_count?.toLocaleString() ?? "—"}
                </span>
              </div>
            </div>
          </div>
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
            <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
              Estimated adjusted
            </h4>
            <div className="space-y-1 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-zinc-600 dark:text-zinc-400">h-index</span>
                <span className="font-bold tabular-nums text-emerald-700 dark:text-emerald-400">
                  {data.adjusted_h_index ?? "—"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-600 dark:text-zinc-400">Citations</span>
                <span className="font-bold tabular-nums text-emerald-700 dark:text-emerald-400">
                  {data.adjusted_citation_count?.toLocaleString() ?? "—"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Auxiliary metrics */}
        <div className="grid grid-cols-3 gap-2 rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs dark:border-zinc-800 dark:bg-zinc-950/40">
          <div className="flex flex-col items-center text-center">
            <span className="text-[10px] uppercase tracking-wide text-zinc-500">
              Self-cite
            </span>
            <span className="font-bold tabular-nums text-zinc-900 dark:text-white">
              {data.self_citation_rate != null
                ? `${(data.self_citation_rate * 100).toFixed(1)}%`
                : "—"}
            </span>
          </div>
          <div className="flex flex-col items-center text-center">
            <span className="text-[10px] uppercase tracking-wide text-zinc-500">
              Topic relevance
            </span>
            <span className="font-bold tabular-nums text-zinc-900 dark:text-white">
              {data.topic_relevance_score != null
                ? `${(data.topic_relevance_score * 100).toFixed(0)}%`
                : "—"}
            </span>
          </div>
          <div className="flex flex-col items-center text-center">
            <span className="text-[10px] uppercase tracking-wide text-zinc-500">
              Publications
            </span>
            <span className="flex items-center gap-1 font-bold tabular-nums text-zinc-900 dark:text-white">
              <BookOpen className="h-3 w-3 text-zinc-500" />
              {data.publications.length}
            </span>
          </div>
        </div>

        {/* Flags list */}
        <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-950/40">
          <h4 className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-500">
            <Users className="h-3 w-3" /> Sample observations {score == null ? "(not assessed)" : `(${flags.length})`}
          </h4>
          {flags.length === 0 ? (
            <p className="text-xs text-zinc-500">{score == null ? "Pattern assessment unavailable." : "No listed sample observations; this does not establish absence of misconduct."}</p>
          ) : (
            <ul className="space-y-1.5">
              {flags.map((flag, i) => (
                <li
                  key={i}
                  className="flex items-start gap-1.5 text-xs text-zinc-700 dark:text-zinc-300"
                >
                  <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-600 dark:text-amber-400" />
                  <span>{flag}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
