"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Users,
  Search,
  Loader2,
  CheckCircle,
  AlertTriangle,
  Clock,
} from "lucide-react";

import { apiFetch, backendUrl } from "@/lib/api";
import { explainIntegrity } from "@/lib/scoreExplanation";
import { ScoreLabel } from "@/components/ui/score-explanation";
import { EmptyState } from "@/components/ui/empty-state";
import type { ProgressEvent, ResearcherListItem } from "@/types/api";
import { scoreColor } from "@/lib/colors";

export default function ResearcherAnalysisPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [scopusId, setScopusId] = useState("");
  const [scholarId, setScholarId] = useState("");
  const [orcid, setOrcid] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [progress, setProgress] = useState(0);
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

      // Start SSE stream — close any prior stream first
      eventSourceRef.current?.close();
      const es = new EventSource(backendUrl(`/api/researcher/${profileId}/stream`));
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

  return (
    <div className="space-y-6">
      <h1 className="font-display text-2xl font-bold text-white">Analyze Researcher</h1>

      <Card className="border-zinc-800 bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="text-lg text-white">Evaluate academic integrity</CardTitle>
          <p className="text-sm text-zinc-400">
            Search by name, Scopus ID, Google Scholar ID, or ORCID
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="researcher-name" className="text-zinc-400">Researcher Name</Label>
            <Input
              id="researcher-name"
              placeholder="e.g. John Smith"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              disabled={loading}
              className="mt-1 border-zinc-700 bg-zinc-800 text-white placeholder:text-zinc-500"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div>
              <Label htmlFor="researcher-scopus" className="text-zinc-400">Scopus ID</Label>
              <Input
                id="researcher-scopus"
                placeholder="e.g. 57203100718"
                value={scopusId}
                onChange={(e) => setScopusId(e.target.value)}
                disabled={loading}
                className="mt-1 border-zinc-700 bg-zinc-800 text-white placeholder:text-zinc-500"
              />
            </div>
            <div>
              <Label htmlFor="researcher-scholar" className="text-zinc-400">Google Scholar ID</Label>
              <Input
                id="researcher-scholar"
                placeholder="e.g. xJaxiEEAAAAJ"
                value={scholarId}
                onChange={(e) => setScholarId(e.target.value)}
                disabled={loading}
                className="mt-1 border-zinc-700 bg-zinc-800 text-white placeholder:text-zinc-500"
              />
            </div>
            <div>
              <Label htmlFor="researcher-orcid" className="text-zinc-400">ORCID</Label>
              <Input
                id="researcher-orcid"
                placeholder="e.g. 0000-0002-1234-5678"
                value={orcid}
                onChange={(e) => setOrcid(e.target.value)}
                disabled={loading}
                className="mt-1 border-zinc-700 bg-zinc-800 text-white placeholder:text-zinc-500"
              />
            </div>
          </div>

          <Button
            onClick={handleSubmit}
            disabled={loading || !hasInput}
            className="w-full bg-purple-500 text-white hover:bg-purple-600"
          >
            {loading ? (
              <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Analyzing...</>
            ) : (
              <><Search className="mr-2 h-4 w-4" /> Analyze Researcher</>
            )}
          </Button>

          {error && (
            <div
              role="alert"
              className="mt-4 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-300"
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
        <Card className="border-zinc-800 bg-zinc-900/50">
          <CardContent className="py-6">
            <div
              role="progressbar"
              aria-label="Researcher analysis progress"
              aria-valuenow={Math.round(progress * 100)}
              aria-valuemin={0}
              aria-valuemax={100}
              className="mb-4 h-2 w-full overflow-hidden rounded-full bg-zinc-800"
            >
              <div
                className="h-full rounded-full bg-purple-500 transition-all duration-300"
                style={{ width: `${progress * 100}%` }}
              />
            </div>
            <div className="space-y-2">
              {events.map((event, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  {event.status === "done" ? (
                    <CheckCircle className="h-4 w-4 shrink-0 text-emerald-400" />
                  ) : event.status === "error" || event.status === "failed" ? (
                    <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
                  ) : event.status === "processing" ? (
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin text-purple-400" />
                  ) : (
                    <Clock className="h-4 w-4 shrink-0 text-zinc-500" />
                  )}
                  <span className="text-zinc-300">{event.detail}</span>
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
  const [analyses, setAnalyses] = useState<ResearcherListItem[]>([]);
  const [loaded, setLoaded] = useState(false);

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
    <Card className="border-zinc-800 bg-zinc-900/50">
      <CardHeader>
        <CardTitle className="text-sm text-zinc-400">Past Analyses</CardTitle>
      </CardHeader>
      <CardContent>
        {!loaded ? (
          <div className="flex justify-center py-8"><Loader2 className="h-6 w-6 animate-spin text-zinc-500" /></div>
        ) : analyses.length === 0 ? (
          <EmptyState
            icon={<Users className="h-5 w-5" />}
            title="No researcher analyses yet"
            description="Search for a researcher above by name, ORCID, or Scopus ID. Results appear here."
          />
        ) : (
          <div className="space-y-3">
            {analyses.map((a) => (
              <a
                key={a.id}
                href={`/researcher/${a.id}`}
                className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-800/30 px-4 py-3 transition hover:border-zinc-700"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-white">{a.researcher_name}</p>
                  <p className="text-xs text-zinc-500">
                    {a.institution || "Unknown institution"} — {new Date(a.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Badge className={
                    a.analysis_status === "completed" ? "bg-emerald-500/20 text-emerald-400"
                    : a.analysis_status === "failed" ? "bg-red-500/20 text-red-400"
                    : "bg-blue-500/20 text-blue-400"
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
              </a>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
