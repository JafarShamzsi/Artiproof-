"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Users,
  Search,
  Loader2,
  CheckCircle,
  AlertTriangle,
  Clock,
  Layers,
  GitCompare,
  ArrowRight,
  UserSearch,
} from "lucide-react";

import { apiFetch, backendUrl } from "@/lib/api";
import { explainIntegrity } from "@/lib/scoreExplanation";
import { ScoreLabel } from "@/components/ui/score-explanation";
import { EmptyState } from "@/components/ui/empty-state";
import { ListSkeleton } from "@/components/ui/skeleton";
import type {
  ProgressEvent,
  ResearcherListItem,
  BulkResearcherResponse,
} from "@/types/api";
import { scoreColor } from "@/lib/colors";
import { toast } from "@/lib/toast";

// Mirrors the backend ORCID_PATTERN — kept in sync with researcher.py.
const ORCID_PATTERN = /^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/;
const ALL_DIGITS = /^\d+$/;

type BulkItem =
  | { researcher_name: string }
  | { scopus_id: string }
  | { orcid: string };

/** Per-line classifier — order matters: ORCID first, then digits, else name. */
function classifyBulkLine(raw: string): BulkItem | null {
  const line = raw.trim();
  if (!line) return null;
  if (ORCID_PATTERN.test(line)) return { orcid: line };
  if (ALL_DIGITS.test(line)) return { scopus_id: line };
  return { researcher_name: line };
}

export default function ResearcherAnalysisPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"single" | "bulk">("single");
  const [name, setName] = useState("");
  const [scopusId, setScopusId] = useState("");
  const [scholarId, setScholarId] = useState("");
  const [orcid, setOrcid] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [progress, setProgress] = useState(0);
  const [bulkInput, setBulkInput] = useState("");
  const [bulkSubmitting, setBulkSubmitting] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Close any in-flight SSE on unmount so we don't leak the connection
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    };
  }, []);

  const hasInput = name || scopusId || scholarId || orcid;

  const handleSubmit = useCallback(async () => {
    if (!hasInput) return;
    setLoading(true);
    setError(null);
    setEvents([]);
    setProgress(0);

    try {
      const res = await apiFetch("/api/researcher/analyze", {
        method: "POST",
        body: JSON.stringify({
          researcher_name: name || null,
          scopus_id: scopusId || null,
          google_scholar_id: scholarId || null,
          orcid: orcid || null,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        setError(err.detail || "Failed to start analysis");
        setLoading(false);
        return;
      }

      const data = await res.json();
      const profileId = data.id;

      // Start SSE stream — close any prior stream first.
      // EventSource can't carry an Authorization header, so we trade the
      // bearer JWT for a one-shot 60s ticket scoped to this profile_id.
      eventSourceRef.current?.close();
      let ticket: string;
      try {
        const ticketRes = await apiFetch(
          `/api/researcher/${profileId}/stream-ticket`,
          { method: "POST" },
        );
        if (!ticketRes.ok) {
          setError(`Stream auth failed (HTTP ${ticketRes.status})`);
          setLoading(false);
          return;
        }
        ticket = ((await ticketRes.json()) as { ticket: string }).ticket;
      } catch {
        setError("Stream auth failed");
        setLoading(false);
        return;
      }
      const es = new EventSource(
        backendUrl(`/api/researcher/${profileId}/stream?ticket=${encodeURIComponent(ticket)}`),
      );
      eventSourceRef.current = es;

      es.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data) as ProgressEvent;
          setEvents((prev) => [...prev, event]);
          setProgress(event.progress);

          if (event.status === "completed" || event.status === "failed") {
            es.close();
            eventSourceRef.current = null;
            setLoading(false);
            if (event.status === "completed") {
              router.push(`/researcher/${profileId}`);
            }
          }
        } catch {
          // Malformed event — ignore
        }
      };

      es.onerror = () => {
        es.close();
        eventSourceRef.current = null;
        setLoading(false);
        if (profileId) {
          router.push(`/researcher/${profileId}`);
        }
      };
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start analysis");
      setLoading(false);
    }
  }, [name, scopusId, scholarId, orcid, hasInput, router]);

  // ─── Bulk submission ───
  // Splits the textarea on newlines, classifies each line as ORCID / scopus_id /
  // researcher_name, then POSTs to /api/researcher/bulk and routes to the
  // batch-progress page with the new profile ids in the query string.
  const handleBulkSubmit = useCallback(async () => {
    setError(null);
    const lines = bulkInput
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
    if (lines.length === 0) {
      setError("Paste at least one researcher name, ORCID, or Scopus ID.");
      return;
    }
    if (lines.length > 50) {
      setError("Bulk runs are limited to 50 researchers per batch.");
      return;
    }
    const items = lines
      .map(classifyBulkLine)
      .filter((x): x is BulkItem => x !== null);
    if (items.length === 0) {
      setError("Couldn't parse any lines — check formatting.");
      return;
    }

    setBulkSubmitting(true);
    try {
      const res = await apiFetch("/api/researcher/bulk", {
        method: "POST",
        body: JSON.stringify({ items }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const msg = err.detail || `Bulk submit failed (HTTP ${res.status})`;
        setError(msg);
        toast.error(msg);
        return;
      }
      const body = (await res.json()) as BulkResearcherResponse;
      const ids = body.items.map((i) => i.id).join(",");
      toast.success(
        `Started ${body.items.length} researcher${body.items.length === 1 ? "" : "s"}`,
      );
      router.push(
        `/researcher/batch/${body.batch_id}?ids=${encodeURIComponent(ids)}`,
      );
    } catch {
      const msg = "Network error — please try again";
      setError(msg);
      toast.error(msg);
    } finally {
      setBulkSubmitting(false);
    }
  }, [bulkInput, router]);

  return (
    <div className="space-y-6">
      <h1 className="font-display text-2xl font-bold text-zinc-900 dark:text-white">Analyze Researcher</h1>

      <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="text-lg text-zinc-900 dark:text-white">Evaluate academic integrity</CardTitle>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Search by name, Scopus ID, Google Scholar ID, or ORCID — or paste many at once.
          </p>
        </CardHeader>
        <CardContent>
          <Tabs
            value={activeTab}
            onValueChange={(v) => {
              setActiveTab(v as "single" | "bulk");
              setError(null);
            }}
          >
            <TabsList className="mb-4 bg-zinc-100 dark:bg-zinc-800">
              <TabsTrigger
                value="single"
                className="data-[state=active]:bg-accent-amber/15 data-[state=active]:text-accent-amber"
              >
                <UserSearch className="mr-2 h-4 w-4" /> Single
              </TabsTrigger>
              <TabsTrigger
                value="bulk"
                className="data-[state=active]:bg-accent-amber/15 data-[state=active]:text-accent-amber"
              >
                <Layers className="mr-2 h-4 w-4" /> Bulk
              </TabsTrigger>
            </TabsList>

            <TabsContent value="single" className="space-y-4">
              <div>
                <Label htmlFor="researcher-name" className="text-zinc-600 dark:text-zinc-400">Researcher Name</Label>
                <Input
                  id="researcher-name"
                  placeholder="e.g. John Smith"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                  disabled={loading}
                  className="mt-1 border-zinc-300 bg-white text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:placeholder:text-zinc-500"
                />
              </div>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <div>
                  <Label htmlFor="researcher-scopus" className="text-zinc-600 dark:text-zinc-400">Scopus ID</Label>
                  <Input
                    id="researcher-scopus"
                    placeholder="e.g. 57203100718"
                    value={scopusId}
                    onChange={(e) => setScopusId(e.target.value)}
                    disabled={loading}
                    className="mt-1 border-zinc-300 bg-white text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:placeholder:text-zinc-500"
                  />
                </div>
                <div>
                  <Label htmlFor="researcher-scholar" className="text-zinc-600 dark:text-zinc-400">Google Scholar ID</Label>
                  <Input
                    id="researcher-scholar"
                    placeholder="e.g. xJaxiEEAAAAJ"
                    value={scholarId}
                    onChange={(e) => setScholarId(e.target.value)}
                    disabled={loading}
                    className="mt-1 border-zinc-300 bg-white text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:placeholder:text-zinc-500"
                  />
                </div>
                <div>
                  <Label htmlFor="researcher-orcid" className="text-zinc-600 dark:text-zinc-400">ORCID</Label>
                  <Input
                    id="researcher-orcid"
                    placeholder="e.g. 0000-0002-1234-5678"
                    value={orcid}
                    onChange={(e) => setOrcid(e.target.value)}
                    disabled={loading}
                    className="mt-1 border-zinc-300 bg-white text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:placeholder:text-zinc-500"
                  />
                </div>
              </div>

              <Button
                onClick={handleSubmit}
                disabled={loading || !hasInput}
                className="w-full bg-accent-amber text-white hover:opacity-90"
              >
                {loading ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Analyzing...</>
                ) : (
                  <><Search className="mr-2 h-4 w-4" /> Analyze Researcher</>
                )}
              </Button>
            </TabsContent>

            <TabsContent value="bulk" className="space-y-4">
              <div className="space-y-3">
                <Textarea
                  placeholder={
                    "Paste researcher names, ORCIDs, or Scopus IDs — one per line"
                  }
                  value={bulkInput}
                  onChange={(e) => setBulkInput(e.target.value)}
                  className="min-h-[200px] border-zinc-300 bg-white font-mono text-xs text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:placeholder:text-zinc-500"
                  disabled={bulkSubmitting}
                />
                <p className="text-xs text-zinc-500">
                  Up to 50 researchers per batch. Lines matching the ORCID
                  pattern are treated as ORCIDs, all-digit lines as Scopus IDs,
                  everything else as researcher names.
                </p>
              </div>

              <Button
                onClick={handleBulkSubmit}
                disabled={bulkSubmitting || !bulkInput.trim()}
                className="w-full bg-accent-amber text-white hover:opacity-90"
              >
                {bulkSubmitting ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Submitting...</>
                ) : (
                  <><Layers className="mr-2 h-4 w-4" /> Run batch</>
                )}
              </Button>
            </TabsContent>
          </Tabs>

          {error && (
            <div
              role="alert"
              className="mt-4 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-700 dark:text-red-300"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Live region for screen readers — announces each pipeline step */}
      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {events.length > 0 ? events[events.length - 1].detail : ""}
      </div>

      {/* Progress */}
      {loading && events.length > 0 && (
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardContent className="py-6">
            <div
              role="progressbar"
              aria-label="Researcher analysis progress"
              aria-valuenow={Math.round(progress * 100)}
              aria-valuemin={0}
              aria-valuemax={100}
              className="mb-4 h-2 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800"
            >
              <div
                className="h-full rounded-full bg-accent-amber transition-all duration-300"
                style={{ width: `${progress * 100}%` }}
              />
            </div>
            <div className="space-y-2">
              {events.map((event, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  {event.status === "done" ? (
                    <CheckCircle className="h-4 w-4 shrink-0 text-emerald-700 dark:text-emerald-400" />
                  ) : event.status === "error" || event.status === "failed" ? (
                    <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
                  ) : event.status === "processing" ? (
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin text-accent-amber" />
                  ) : (
                    <Clock className="h-4 w-4 shrink-0 text-zinc-500" />
                  )}
                  <span className="text-zinc-700 dark:text-zinc-300">{event.detail}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Past Analyses */}
      {!loading && <PastAnalyses />}
    </div>
  );
}

function PastAnalyses() {
  const router = useRouter();
  const [analyses, setAnalyses] = useState<ResearcherListItem[]>([]);
  const [loaded, setLoaded] = useState(false);

  // Compare mode mirrors the source-check pattern: ephemeral, not URL-backed,
  // capped at exactly two selections.
  const [compareMode, setCompareMode] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);

  const toggleSelected = useCallback((id: string) => {
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      // Cap at 2 — comparison view is strictly side-by-side.
      if (prev.length >= 2) return [prev[1], id];
      return [...prev, id];
    });
  }, []);

  const goCompare = useCallback(() => {
    if (selected.length !== 2) return;
    router.push(`/researcher/compare?a=${selected[0]}&b=${selected[1]}`);
  }, [router, selected]);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const r = await apiFetch("/api/researcher/", { signal: controller.signal });
        if (!r.ok) return;
        const data = await r.json();
        setAnalyses(data.items || []);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
      } finally {
        setLoaded(true);
      }
    })();
    return () => controller.abort();
  }, []);

  return (
    <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
      <CardHeader className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-sm text-zinc-600 dark:text-zinc-400">Past Analyses</CardTitle>
          <Button
            variant={compareMode ? "default" : "outline"}
            size="sm"
            onClick={() => {
              setCompareMode((v) => !v);
              if (compareMode) setSelected([]);
            }}
            className={
              compareMode
                ? "bg-accent-amber text-white hover:opacity-90"
                : "border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-400"
            }
          >
            <GitCompare className="mr-1.5 h-4 w-4" />
            {compareMode ? "Done comparing" : "Compare"}
          </Button>
        </div>

        {compareMode && (
          <div className="flex flex-wrap items-center gap-2 rounded-md border border-accent-amber/20 bg-accent-amber/5 px-3 py-2 text-xs">
            <span className="text-zinc-700 dark:text-zinc-300">
              {selected.length === 0
                ? "Select two analyses to compare side-by-side."
                : selected.length === 1
                  ? "Select one more to compare."
                  : "Two selected."}
            </span>
            {selected.length === 2 && (
              <Button
                size="sm"
                onClick={goCompare}
                className="ml-auto bg-accent-amber text-white hover:opacity-90"
              >
                Compare these <ArrowRight className="ml-1 h-3 w-3" />
              </Button>
            )}
          </div>
        )}
      </CardHeader>
      <CardContent>
        {!loaded ? (
          <ListSkeleton rows={3} />
        ) : analyses.length === 0 ? (
          <EmptyState
            icon={<Users className="h-5 w-5" />}
            title="No researcher analyses yet"
            description="Search for a researcher above by name, ORCID, or Scopus ID. Results appear here."
          />
        ) : (
          <div className="space-y-3">
            {analyses.map((a) => (
              <PastAnalysisRow
                key={a.id}
                analysis={a}
                compareMode={compareMode}
                selected={selected.includes(a.id)}
                onToggleSelect={() => toggleSelected(a.id)}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function PastAnalysisRow({
  analysis: a,
  compareMode,
  selected,
  onToggleSelect,
}: {
  analysis: ResearcherListItem;
  compareMode: boolean;
  selected: boolean;
  onToggleSelect: () => void;
}) {
  const inner = (
    <>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-zinc-900 dark:text-white">{a.researcher_name}</p>
        <p className="text-xs text-zinc-500">
          {a.institution || "Unknown institution"} — {new Date(a.created_at).toLocaleDateString()}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <Badge className={
          a.analysis_status === "completed" ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400"
          : a.analysis_status === "failed" ? "bg-red-500/20 text-red-700 dark:text-red-400"
          : "bg-blue-500/20 text-blue-700 dark:text-blue-400"
        }>
          {a.analysis_status}
        </Badge>
        {a.integrity_score !== null && (
          <div className="flex items-center gap-2">
            <ScoreLabel
              explanation={explainIntegrity({ score: a.integrity_score })}
            />
            <span className={`text-lg font-bold ${scoreColor(a.integrity_score)}`}>
              {Math.round(a.integrity_score)}
            </span>
          </div>
        )}
      </div>
    </>
  );

  if (compareMode) {
    return (
      <button
        type="button"
        onClick={onToggleSelect}
        aria-pressed={selected}
        className={
          "flex w-full items-center justify-between rounded-lg border bg-zinc-50 px-4 py-3 text-left transition dark:bg-zinc-800/30 " +
          (selected
            ? "border-accent-amber ring-2 ring-accent-amber/30"
            : "border-zinc-200 hover:border-zinc-300 dark:border-zinc-800 dark:hover:border-zinc-700")
        }
      >
        <div className="mr-3 flex h-5 w-5 shrink-0 items-center justify-center rounded border border-zinc-300 dark:border-zinc-700">
          {selected && <CheckCircle className="h-4 w-4 text-accent-amber" />}
        </div>
        {inner}
      </button>
    );
  }

  return (
    <a
      href={`/researcher/${a.id}`}
      className="flex items-center justify-between rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 transition hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-800/30 dark:hover:border-zinc-700"
    >
      {inner}
    </a>
  );
}
