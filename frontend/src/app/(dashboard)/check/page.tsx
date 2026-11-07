"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
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
} from "lucide-react";
import { apiFetch, backendUrl } from "@/lib/api";
import { explainCredibility } from "@/lib/scoreExplanation";
import { ScoreLabel } from "@/components/ui/score-explanation";
import { EmptyState } from "@/components/ui/empty-state";
import { ListSkeleton } from "@/components/ui/skeleton";
import type { ProgressEvent, SourceCheckListItem } from "@/types/api";
import { scoreColor } from "@/lib/colors";

export default function CheckSourcePage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState("url");
  const [inputValue, setInputValue] = useState("");
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

  const startSSE = useCallback((checkId: string) => {
    // If a previous run is still streaming, close it first
    eventSourceRef.current?.close();
    const es = new EventSource(backendUrl(`/api/source-check/${checkId}/stream`));
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
            router.push(`/check/${checkId}`);
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
        startSSE(data.id);
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
        startSSE(data.id);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to start analysis");
        setLoading(false);
      }
    }
  }, [inputValue, activeTab, selectedFile, startSSE]);

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
            }}
          >
            <TabsList className="mb-4 bg-zinc-100 dark:bg-zinc-800">
              <TabsTrigger
                value="url"
                className="data-[state=active]:bg-brand/15 data-[state=active]:text-brand dark:data-[state=active]:text-brand-fg"
              >
                <Link2 className="mr-2 h-4 w-4" /> Paste URL
              </TabsTrigger>
              <TabsTrigger
                value="text"
                className="data-[state=active]:bg-brand/15 data-[state=active]:text-brand dark:data-[state=active]:text-brand-fg"
              >
                <FileText className="mr-2 h-4 w-4" /> Paste Text
              </TabsTrigger>
              <TabsTrigger
                value="document"
                className="data-[state=active]:bg-brand/15 data-[state=active]:text-brand dark:data-[state=active]:text-brand-fg"
              >
                <Upload className="mr-2 h-4 w-4" /> Upload PDF
              </TabsTrigger>
            </TabsList>

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
          </Tabs>

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

      {/* Past Checks */}
      {!loading && <PastChecks />}
    </div>
  );
}

function PastChecks() {
  const [checks, setChecks] = useState<SourceCheckListItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const r = await apiFetch("/api/source-check/", { signal: controller.signal });
        if (!r.ok) {
          setLoadError(`Failed to load past checks (HTTP ${r.status})`);
          return;
        }
        const data = await r.json();
        setChecks(data.items || []);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setLoadError(e instanceof Error ? e.message : "Failed to load past checks");
      } finally {
        setLoaded(true);
      }
    })();
    return () => controller.abort();
  }, []);

  return (
    <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
      <CardHeader>
        <CardTitle className="text-sm text-zinc-600 dark:text-zinc-400">
          Past Source Checks
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!loaded ? (
          <ListSkeleton rows={3} />
        ) : loadError ? (
          <div className="flex flex-col items-center py-8 text-sm text-red-700 dark:text-red-300">
            <AlertTriangle className="mb-3 h-10 w-10" />
            {loadError}
          </div>
        ) : checks.length === 0 ? (
          <EmptyState
            icon={<Shield className="h-5 w-5" />}
            title="No source checks yet"
            description="Run your first source check above. Results will appear here."
          />
        ) : (
          <div className="space-y-3">
            {checks.map((check) => (
              <a
                key={check.id}
                href={`/check/${check.id}`}
                className="flex items-center justify-between rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 transition hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-800/30 dark:hover:border-zinc-700"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-zinc-900 dark:text-white">
                    {check.input_title ||
                      check.input_type.toUpperCase()}
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
              </a>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
