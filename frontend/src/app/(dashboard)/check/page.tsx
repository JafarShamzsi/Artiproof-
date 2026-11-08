"use client";

import { useState, useEffect, useRef, useCallback, useMemo, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Search,
  Link2,
  FileText,
  Upload,
  Loader2,
  CheckCircle,
  AlertTriangle,
  Clock,
  Shield,
  File as FileIcon,
  X,
  Layers,
  GitCompare,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { apiFetch, backendUrl } from "@/lib/api";
import { explainCredibility } from "@/lib/scoreExplanation";
import { ScoreLabel } from "@/components/ui/score-explanation";
import { EmptyState } from "@/components/ui/empty-state";
import { ListSkeleton } from "@/components/ui/skeleton";
import type { ProgressEvent, SourceCheckListItem, SourceCheckListResponse, BulkSourceCheckResponse } from "@/types/api";
import { scoreColor } from "@/lib/colors";
import { toast } from "@/lib/toast";

// ─── Sort key constants — kept in sync with the backend's `SortKey` literal. ───
const SORT_OPTIONS = [
  { value: "created_at_desc", label: "Newest" },
  { value: "created_at_asc", label: "Oldest" },
  { value: "score_desc", label: "Highest score" },
  { value: "score_asc", label: "Lowest score" },
] as const;

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "pending", label: "Pending" },
  { value: "processing", label: "Processing" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
] as const;

const PAGE_SIZE_OPTIONS = [20, 50, 100];

export default function CheckSourcePage() {
  return (
    // Suspense boundary required because the inner client tree calls
    // `useSearchParams()`. Without it, Next 16's static-build pass throws
    // ("useSearchParams should be wrapped in a suspense boundary").
    <Suspense fallback={<div className="space-y-6"><div className="h-8 w-48 animate-pulse rounded bg-zinc-200 dark:bg-zinc-800" /><div className="h-64 animate-pulse rounded-lg bg-zinc-200 dark:bg-zinc-800" /></div>}>
      <CheckSourcePageInner />
    </Suspense>
  );
}

function CheckSourcePageInner() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState("url");
  const [inputValue, setInputValue] = useState("");
  const [bulkInput, setBulkInput] = useState("");
  const [bulkSubmitting, setBulkSubmitting] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [progress, setProgress] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Hold the active EventSource so unmount can close it.
  const eventSourceRef = useRef<EventSource | null>(null);

  // Clean up any in-flight SSE stream when this component unmounts.
  // Without this the connection keeps streaming events into a detached
  // setEvents and eventually leaks memory + holds an HTTP connection open.
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    };
  }, []);

  const startSSE = useCallback(async (checkId: string) => {
    // If a previous run is still streaming, close it first
    eventSourceRef.current?.close();
    // EventSource can't carry an Authorization header, so we trade the
    // bearer JWT for a one-shot 60s ticket scoped to this check_id.
    let ticket: string;
    try {
      const ticketRes = await apiFetch(
        `/api/source-check/${checkId}/stream-ticket`,
        { method: "POST" },
      );
      if (!ticketRes.ok) {
        setLoading(false);
        router.push(`/check/${checkId}`);
        return;
      }
      ticket = ((await ticketRes.json()) as { ticket: string }).ticket;
    } catch {
      setLoading(false);
      router.push(`/check/${checkId}`);
      return;
    }
    const es = new EventSource(
      backendUrl(`/api/source-check/${checkId}/stream?ticket=${encodeURIComponent(ticket)}`),
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
          router.push(`/check/${checkId}`);
        }
      } catch {
        // Malformed event — ignore
      }
    };

    es.onerror = () => {
      // EventSource may fire onerror for two reasons:
      //   - normal stream end (readyState === CLOSED) — the server
      //     finished pushing events and closed the connection. Navigate
      //     to the result page silently.
      //   - actual connection drop (CONNECTING/OPEN with no data) —
      //     the user needs to know the live progress was interrupted,
      //     otherwise they'll wait on a stale spinner.
      const wasCleanClose = es.readyState === EventSource.CLOSED;
      es.close();
      eventSourceRef.current = null;
      setLoading(false);
      if (!wasCleanClose) {
        toast.error(
          "Live progress disconnected. Opening the result page — your analysis is still running."
        );
      }
      router.push(`/check/${checkId}`);
    };
  }, [router]);

  const handleSubmit = useCallback(async () => {
    setError(null);
    if (activeTab === "document") {
      if (!selectedFile) return;
      setLoading(true);
      setEvents([]);
      setProgress(0);

      try {
        const formData = new FormData();
        formData.append("file", selectedFile);

        const res = await apiFetch("/api/source-check/upload", {
          method: "POST",
          body: formData,
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: "Upload failed" }));
          setError(err.detail || `Upload failed (HTTP ${res.status})`);
          setLoading(false);
          return;
        }

        const data = await res.json();
        await startSSE(data.id);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed");
        setLoading(false);
      }
    } else {
      if (!inputValue.trim()) return;
      setLoading(true);
      setEvents([]);
      setProgress(0);

      try {
        const res = await apiFetch("/api/source-check/", {
          method: "POST",
          body: JSON.stringify({
            input_type: activeTab,
            input_content: inputValue.trim(),
          }),
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
          setError(err.detail || "Failed to start analysis");
          setLoading(false);
          return;
        }

        const data = await res.json();
        await startSSE(data.id);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to start analysis");
        setLoading(false);
      }
    }
  }, [inputValue, activeTab, selectedFile, startSSE]);

  // ─── Bulk submission ───
  // Splits the textarea on newlines, filters empties, classifies each line as
  // url vs text by regex, then POSTs to /api/source-check/bulk and routes to
  // the batch-progress page with the new check ids in the query string.
  const handleBulkSubmit = useCallback(async () => {
    setError(null);
    const lines = bulkInput
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
    if (lines.length === 0) {
      setError("Paste at least one URL or piece of text.");
      return;
    }
    if (lines.length > 50) {
      setError("Bulk runs are limited to 50 items per batch.");
      return;
    }
    const items = lines.map((line) => ({
      input_type: /^https?:\/\//i.test(line) ? "url" : "text",
      input_content: line,
    }));
    setBulkSubmitting(true);
    try {
      const res = await apiFetch("/api/source-check/bulk", {
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
      const body = (await res.json()) as BulkSourceCheckResponse;
      const ids = body.items.map((i) => i.id).join(",");
      toast.success(`Started ${body.items.length} check${body.items.length === 1 ? "" : "s"}`);
      router.push(`/check/batch/${body.batch_id}?ids=${encodeURIComponent(ids)}`);
    } catch {
      const msg = "Network error — please try again";
      setError(msg);
      toast.error(msg);
    } finally {
      setBulkSubmitting(false);
    }
  }, [bulkInput, router]);

  const canSubmit =
    activeTab === "document" ? !!selectedFile : !!inputValue.trim();

  return (
    <div className="space-y-6">
      <h1 className="font-display text-2xl font-bold text-zinc-900 dark:text-white">Check Source</h1>

      <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="text-lg text-zinc-900 dark:text-white">
            Verify a source for misinformation and AI content
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs
            value={activeTab}
            onValueChange={(v) => {
              setActiveTab(v);
              setInputValue("");
              setSelectedFile(null);
              setError(null);
            }}
          >
            {/* Tabs scroll horizontally on narrow viewports so they
                never overflow the page. The wrapper handles touch
                scrolling on mobile while keeping the desktop layout
                identical. */}
            <div className="-mx-1 mb-4 overflow-x-auto pb-1">
              <TabsList className="bg-zinc-100 dark:bg-zinc-800">
                <TabsTrigger
                  value="url"
                  className="whitespace-nowrap data-[state=active]:bg-brand/15 data-[state=active]:text-brand dark:data-[state=active]:text-brand-fg"
                >
                  <Link2 className="mr-2 h-4 w-4" /> Paste URL
                </TabsTrigger>
                <TabsTrigger
                  value="text"
                  className="whitespace-nowrap data-[state=active]:bg-brand/15 data-[state=active]:text-brand dark:data-[state=active]:text-brand-fg"
                >
                  <FileText className="mr-2 h-4 w-4" /> Paste Text
                </TabsTrigger>
                <TabsTrigger
                  value="document"
                  className="whitespace-nowrap data-[state=active]:bg-brand/15 data-[state=active]:text-brand dark:data-[state=active]:text-brand-fg"
                >
                  <Upload className="mr-2 h-4 w-4" /> Upload PDF
                </TabsTrigger>
                <TabsTrigger
                  value="bulk"
                  className="whitespace-nowrap data-[state=active]:bg-brand/15 data-[state=active]:text-brand dark:data-[state=active]:text-brand-fg"
                >
                  <Layers className="mr-2 h-4 w-4" /> Bulk
                </TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="url">
              <Input
                placeholder="https://example.com/article..."
                value={activeTab === "url" ? inputValue : ""}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                className="border-zinc-300 bg-white text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:placeholder:text-zinc-500"
                disabled={loading}
              />
            </TabsContent>

            <TabsContent value="text">
              <Textarea
                placeholder="Paste the article text here..."
                value={activeTab === "text" ? inputValue : ""}
                onChange={(e) => setInputValue(e.target.value)}
                className="min-h-[200px] border-zinc-300 bg-white text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:placeholder:text-zinc-500"
                disabled={loading}
              />
            </TabsContent>

            <TabsContent value="document">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) setSelectedFile(file);
                }}
                disabled={loading}
              />

              {selectedFile ? (
                <div className="flex items-center gap-3 rounded-lg border border-zinc-300 bg-zinc-50 px-4 py-3 dark:border-zinc-700 dark:bg-zinc-800">
                  <FileIcon className="h-8 w-8 shrink-0 text-red-600 dark:text-red-400" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-zinc-900 dark:text-white">
                      {selectedFile.name}
                    </p>
                    <p className="text-xs text-zinc-500">
                      {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setSelectedFile(null);
                      if (fileInputRef.current) fileInputRef.current.value = "";
                    }}
                    aria-label="Remove selected file"
                    className="h-8 w-8 p-0 text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white"
                    disabled={loading}
                  >
                    <X aria-hidden="true" className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  aria-label="Upload PDF file"
                  className="flex w-full flex-col items-center justify-center rounded-lg border-2 border-dashed border-zinc-300 py-12 transition hover:border-brand/50 focus-visible:border-brand/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/40 dark:border-zinc-700"
                  disabled={loading}
                >
                  <Upload aria-hidden="true" className="mb-3 h-8 w-8 text-zinc-500" />
                  <p className="text-sm text-zinc-600 dark:text-zinc-400">
                    Click to select a PDF file
                  </p>
                  <p className="mt-1 text-xs text-zinc-500">
                    PDF files up to 50MB
                  </p>
                </button>
              )}
            </TabsContent>

            <TabsContent value="bulk">
              <div className="space-y-3">
                <Textarea
                  placeholder={
                    "https://example.com/article-1\nhttps://example.com/article-2\nA piece of text to fact-check, one item per line"
                  }
                  value={bulkInput}
                  onChange={(e) => setBulkInput(e.target.value)}
                  className="min-h-[200px] border-zinc-300 bg-white font-mono text-xs text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white dark:placeholder:text-zinc-500"
                  disabled={bulkSubmitting}
                />
                <p className="text-xs text-zinc-500">
                  Paste up to 50 URLs or pieces of text, one per line. Lines starting with{" "}
                  <code className="rounded bg-zinc-100 px-1 py-0.5 dark:bg-zinc-800">http://</code>{" "}
                  or <code className="rounded bg-zinc-100 px-1 py-0.5 dark:bg-zinc-800">https://</code>{" "}
                  are treated as URLs; everything else is analyzed as text.
                </p>
                <p className="text-xs text-zinc-500">
                  PDF bulk upload coming next — for now use the Upload PDF tab one at a time.
                </p>
              </div>
            </TabsContent>
          </Tabs>

          {activeTab === "bulk" ? (
            <Button
              onClick={handleBulkSubmit}
              disabled={bulkSubmitting || !bulkInput.trim()}
              className="mt-4 w-full bg-brand text-white hover:bg-brand-hover"
            >
              {bulkSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Submitting...
                </>
              ) : (
                <>
                  <Layers className="mr-2 h-4 w-4" /> Run batch
                </>
              )}
            </Button>
          ) : (
            <Button
              onClick={handleSubmit}
              disabled={loading || !canSubmit}
              className="mt-4 w-full bg-brand text-white hover:bg-brand-hover"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Analyzing...
                </>
              ) : (
                <>
                  <Search className="mr-2 h-4 w-4" /> Analyze
                </>
              )}
            </Button>
          )}

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
              aria-label="Analysis progress"
              aria-valuenow={Math.round(progress * 100)}
              aria-valuemin={0}
              aria-valuemax={100}
              className="mb-4 h-2 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800"
            >
              <div
                className="h-full rounded-full bg-brand transition-all duration-300"
                style={{ width: `${progress * 100}%` }}
              />
            </div>
            <div className="space-y-2">
              {events.map((event, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  {event.status === "done" ? (
                    <CheckCircle className="h-4 w-4 shrink-0 text-emerald-700 dark:text-emerald-400" />
                  ) : event.status === "error" || event.status === "warning" ? (
                    <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
                  ) : event.status === "processing" ? (
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin text-blue-600 dark:text-blue-400" />
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

      {/* Past Checks — extended list with search/filter/sort/pagination + compare */}
      {!loading && <PastChecks />}
    </div>
  );
}

// ─── Past Checks list ───

function PastChecks() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Read filter state from URL — single source of truth so the back button
  // and sharing of filtered links both work.
  const q = searchParams.get("q") ?? "";
  const minScoreParam = searchParams.get("min_score");
  const maxScoreParam = searchParams.get("max_score");
  const status = searchParams.get("status") ?? "";
  const sort = searchParams.get("sort") ?? "created_at_desc";
  const page = Math.max(1, parseInt(searchParams.get("page") ?? "1", 10) || 1);
  const pageSize = (() => {
    const v = parseInt(searchParams.get("page_size") ?? "20", 10);
    return PAGE_SIZE_OPTIONS.includes(v) ? v : 20;
  })();

  // Local-only echo state for typing — flushed to the URL on debounce.
  const [searchInput, setSearchInput] = useState(q);
  const [minScoreInput, setMinScoreInput] = useState(minScoreParam ?? "");
  const [maxScoreInput, setMaxScoreInput] = useState(maxScoreParam ?? "");

  // Keep the input echoes in sync if the URL changes externally (back/forward).
  useEffect(() => setSearchInput(q), [q]);
  useEffect(() => setMinScoreInput(minScoreParam ?? ""), [minScoreParam]);
  useEffect(() => setMaxScoreInput(maxScoreParam ?? ""), [maxScoreParam]);

  // Helpers to mutate the URL state without losing other params.
  const updateParams = useCallback(
    (mutate: (params: URLSearchParams) => void) => {
      const params = new URLSearchParams(searchParams.toString());
      mutate(params);
      router.replace(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  // Debounce the search box → q query param. 300ms keeps typing fluid while
  // avoiding a request per keystroke.
  useEffect(() => {
    if (searchInput === q) return;
    const t = setTimeout(() => {
      updateParams((p) => {
        if (searchInput.trim()) p.set("q", searchInput.trim());
        else p.delete("q");
        // Reset to page 1 whenever the filter changes.
        p.delete("page");
      });
    }, 300);
    return () => clearTimeout(t);
  }, [searchInput, q, updateParams]);

  const commitScore = useCallback(
    (which: "min_score" | "max_score", raw: string) => {
      const trimmed = raw.trim();
      const n = trimmed === "" ? null : Number(trimmed);
      updateParams((p) => {
        if (n == null || Number.isNaN(n)) p.delete(which);
        else p.set(which, String(Math.max(0, Math.min(100, n))));
        p.delete("page");
      });
    },
    [updateParams],
  );

  // ─── Comparison mode ───
  // Separate from the URL because the selected ids are ephemeral — a user
  // shouldn't get redirected back into "select two" mode by sharing a link.
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
    router.push(`/check/compare?a=${selected[0]}&b=${selected[1]}`);
  }, [router, selected]);

  // ─── Fetch list whenever any URL filter changes ───
  const [response, setResponse] = useState<SourceCheckListResponse | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Build the canonical query string for the backend list endpoint.
  const apiQuery = useMemo(() => {
    const p = new URLSearchParams();
    if (q.trim()) p.set("q", q.trim());
    if (minScoreParam != null && minScoreParam !== "") p.set("min_score", minScoreParam);
    if (maxScoreParam != null && maxScoreParam !== "") p.set("max_score", maxScoreParam);
    if (status) p.set("status", status);
    p.set("sort", sort);
    p.set("page", String(page));
    p.set("page_size", String(pageSize));
    return p.toString();
  }, [q, minScoreParam, maxScoreParam, status, sort, page, pageSize]);

  useEffect(() => {
    const controller = new AbortController();
    setLoaded(false);
    setLoadError(null);
    (async () => {
      try {
        const r = await apiFetch(`/api/source-check/?${apiQuery}`, { signal: controller.signal });
        if (!r.ok) {
          setLoadError(`Failed to load past checks (HTTP ${r.status})`);
          return;
        }
        const data = (await r.json()) as SourceCheckListResponse;
        setResponse(data);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setLoadError(e instanceof Error ? e.message : "Failed to load past checks");
      } finally {
        setLoaded(true);
      }
    })();
    return () => controller.abort();
  }, [apiQuery]);

  const total = response?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const items = response?.items ?? [];

  return (
    <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
      <CardHeader className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-sm text-zinc-600 dark:text-zinc-400">
            Past Source Checks
          </CardTitle>
          <Button
            variant={compareMode ? "default" : "outline"}
            size="sm"
            onClick={() => {
              setCompareMode((v) => !v);
              if (compareMode) setSelected([]);
            }}
            className={
              compareMode
                ? "bg-brand text-white hover:bg-brand-hover"
                : "border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-400"
            }
          >
            <GitCompare className="mr-1.5 h-4 w-4" />
            {compareMode ? "Done comparing" : "Compare"}
          </Button>
        </div>

        {/* Compare-mode banner with the "Compare these →" CTA */}
        {compareMode && (
          <div className="flex flex-wrap items-center gap-2 rounded-md border border-brand/20 bg-brand/5 px-3 py-2 text-xs">
            <span className="text-zinc-700 dark:text-zinc-300">
              {selected.length === 0
                ? "Select two checks to compare side-by-side."
                : selected.length === 1
                  ? "Select one more to compare."
                  : "Two selected."}
            </span>
            {selected.length === 2 && (
              <Button
                size="sm"
                onClick={goCompare}
                className="ml-auto bg-brand text-white hover:bg-brand-hover"
              >
                Compare these <ArrowRight className="ml-1 h-3 w-3" />
              </Button>
            )}
          </div>
        )}

        {/* Filter row */}
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-6">
          <div className="lg:col-span-2">
            <label htmlFor="past-checks-search" className="sr-only">
              Search past checks
            </label>
            <Input
              id="past-checks-search"
              placeholder="Search title or content..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="border-zinc-300 bg-white text-sm dark:border-zinc-700 dark:bg-zinc-800"
            />
          </div>
          <div className="grid grid-cols-2 gap-2 lg:col-span-2">
            <Input
              type="number"
              min={0}
              max={100}
              step={1}
              placeholder="Min"
              aria-label="Minimum score"
              value={minScoreInput}
              onChange={(e) => setMinScoreInput(e.target.value)}
              onBlur={(e) => commitScore("min_score", e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && commitScore("min_score", e.currentTarget.value)}
              className="border-zinc-300 bg-white text-sm dark:border-zinc-700 dark:bg-zinc-800"
            />
            <Input
              type="number"
              min={0}
              max={100}
              step={1}
              placeholder="Max"
              aria-label="Maximum score"
              value={maxScoreInput}
              onChange={(e) => setMaxScoreInput(e.target.value)}
              onBlur={(e) => commitScore("max_score", e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && commitScore("max_score", e.currentTarget.value)}
              className="border-zinc-300 bg-white text-sm dark:border-zinc-700 dark:bg-zinc-800"
            />
          </div>
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(e) => {
              const v = e.target.value;
              updateParams((p) => {
                if (v) p.set("status", v);
                else p.delete("status");
                p.delete("page");
              });
            }}
            className="h-9 rounded-md border border-zinc-300 bg-white px-2 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            aria-label="Sort order"
            value={sort}
            onChange={(e) => {
              const v = e.target.value;
              updateParams((p) => {
                p.set("sort", v);
                p.delete("page");
              });
            }}
            className="h-9 rounded-md border border-zinc-300 bg-white px-2 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800 dark:text-white"
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </CardHeader>
      <CardContent>
        {!loaded ? (
          <ListSkeleton rows={3} />
        ) : loadError ? (
          <div className="flex flex-col items-center py-8 text-sm text-red-700 dark:text-red-300">
            <AlertTriangle className="mb-3 h-10 w-10" />
            {loadError}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={<Shield className="h-5 w-5" />}
            title={q || status || minScoreParam || maxScoreParam ? "No matches" : "No source checks yet"}
            description={
              q || status || minScoreParam || maxScoreParam
                ? "Try clearing or relaxing the filters."
                : "Run your first source check above — paste a URL, text, or PDF. Results will appear here."
            }
            action={
              q || status || minScoreParam || maxScoreParam
                ? undefined
                : { label: "See a sample report", href: "/demo" }
            }
          />
        ) : (
          <div className="space-y-3">
            {items.map((check) => (
              <PastCheckRow
                key={check.id}
                check={check}
                compareMode={compareMode}
                selected={selected.includes(check.id)}
                onToggleSelect={() => toggleSelected(check.id)}
              />
            ))}
          </div>
        )}

        {/* Pagination */}
        {loaded && !loadError && total > 0 && (
          <Pagination
            page={page}
            pageSize={pageSize}
            totalPages={totalPages}
            total={total}
            onChangePage={(next) =>
              updateParams((p) => {
                if (next <= 1) p.delete("page");
                else p.set("page", String(next));
              })
            }
            onChangePageSize={(size) =>
              updateParams((p) => {
                if (size === 20) p.delete("page_size");
                else p.set("page_size", String(size));
                p.delete("page");
              })
            }
          />
        )}
      </CardContent>
    </Card>
  );
}

// ── Past-check row (selectable in compare mode, link otherwise). ──

function PastCheckRow({
  check,
  compareMode,
  selected,
  onToggleSelect,
}: {
  check: SourceCheckListItem;
  compareMode: boolean;
  selected: boolean;
  onToggleSelect: () => void;
}) {
  const inner = (
    <>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-zinc-900 dark:text-white">
          {check.input_title || check.input_type.toUpperCase()}
        </p>
        <p className="text-xs text-zinc-500">
          {new Date(check.created_at).toLocaleDateString()}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <Badge
          className={
            check.status === "completed"
              ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400"
              : check.status === "failed"
                ? "bg-red-500/20 text-red-700 dark:text-red-400"
                : "bg-blue-500/20 text-blue-700 dark:text-blue-400"
          }
        >
          {check.status}
        </Badge>
        {check.overall_credibility_score !== null && (
          <div className="flex items-center gap-2">
            <ScoreLabel
              explanation={explainCredibility({
                score: check.overall_credibility_score,
              })}
            />
            <span
              className={`text-lg font-bold ${scoreColor(check.overall_credibility_score)}`}
            >
              {Math.round(check.overall_credibility_score)}
            </span>
          </div>
        )}
      </div>
    </>
  );

  // Compare mode replaces the link with a button-like row that toggles
  // selection state. Selected rows get a brand-tinted ring.
  if (compareMode) {
    return (
      <button
        type="button"
        onClick={onToggleSelect}
        aria-pressed={selected}
        className={
          "flex w-full items-center justify-between rounded-lg border bg-zinc-50 px-4 py-3 text-left transition dark:bg-zinc-800/30 " +
          (selected
            ? "border-brand ring-2 ring-brand/30 dark:border-brand-fg"
            : "border-zinc-200 hover:border-zinc-300 dark:border-zinc-800 dark:hover:border-zinc-700")
        }
      >
        <div className="mr-3 flex h-5 w-5 shrink-0 items-center justify-center rounded border border-zinc-300 dark:border-zinc-700">
          {selected && <CheckCircle className="h-4 w-4 text-brand dark:text-brand-fg" />}
        </div>
        {inner}
      </button>
    );
  }

  return (
    <a
      href={`/check/${check.id}`}
      className="flex items-center justify-between rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 transition hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-800/30 dark:hover:border-zinc-700"
    >
      {inner}
    </a>
  );
}

// ── Pagination control ──

function Pagination({
  page,
  pageSize,
  totalPages,
  total,
  onChangePage,
  onChangePageSize,
}: {
  page: number;
  pageSize: number;
  totalPages: number;
  total: number;
  onChangePage: (next: number) => void;
  onChangePageSize: (size: number) => void;
}) {
  // Page-number buttons: show 1 … (cluster around current) … N when there
  // are >5 pages, otherwise just list them all.
  const pageButtons: (number | "ellipsis-left" | "ellipsis-right")[] = useMemo(() => {
    if (totalPages <= 5) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }
    const first = 1;
    const last = totalPages;
    const around: number[] = [];
    for (let i = page - 1; i <= page + 1; i++) {
      if (i > first && i < last) around.push(i);
    }
    const out: (number | "ellipsis-left" | "ellipsis-right")[] = [first];
    if (around[0] && around[0] > first + 1) out.push("ellipsis-left");
    out.push(...around);
    if (around[around.length - 1] && around[around.length - 1] < last - 1)
      out.push("ellipsis-right");
    out.push(last);
    return out;
  }, [page, totalPages]);

  return (
    <nav
      aria-label="Pagination"
      className="mt-4 flex flex-col items-center justify-between gap-3 border-t border-zinc-200 pt-4 sm:flex-row dark:border-zinc-800"
    >
      <div className="flex items-center gap-2 text-xs text-zinc-500">
        <span>
          {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, total)} of {total}
        </span>
        <label className="ml-3 flex items-center gap-1">
          <span className="text-zinc-500">Per page</span>
          <select
            value={pageSize}
            onChange={(e) => onChangePageSize(Number(e.target.value))}
            aria-label="Items per page"
            className="h-7 rounded border border-zinc-300 bg-white px-1 text-xs dark:border-zinc-700 dark:bg-zinc-800"
          >
            {PAGE_SIZE_OPTIONS.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="flex items-center gap-1">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onChangePage(page - 1)}
          disabled={page <= 1}
          aria-label="Previous page"
          className="h-8 border-zinc-300 px-2 text-xs dark:border-zinc-700"
        >
          <ChevronLeft className="h-3 w-3" /> Previous
        </Button>
        <span className="px-2 text-xs text-zinc-500">
          Page {page} of {totalPages}
        </span>
        {totalPages > 5 && (
          <div className="hidden items-center gap-0.5 sm:flex">
            {pageButtons.map((b, i) =>
              typeof b === "number" ? (
                <button
                  key={`p-${b}-${i}`}
                  type="button"
                  onClick={() => onChangePage(b)}
                  aria-current={b === page ? "page" : undefined}
                  className={
                    "h-7 min-w-7 rounded border px-1.5 text-xs " +
                    (b === page
                      ? "border-brand bg-brand/10 text-brand dark:text-brand-fg"
                      : "border-zinc-300 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800")
                  }
                >
                  {b}
                </button>
              ) : (
                <span
                  key={`e-${b}-${i}`}
                  aria-hidden="true"
                  className="px-1 text-xs text-zinc-400"
                >
                  …
                </span>
              ),
            )}
          </div>
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={() => onChangePage(page + 1)}
          disabled={page >= totalPages}
          aria-label="Next page"
          className="h-8 border-zinc-300 px-2 text-xs dark:border-zinc-700"
        >
          Next <ChevronRight className="h-3 w-3" />
        </Button>
      </div>
    </nav>
  );
}
