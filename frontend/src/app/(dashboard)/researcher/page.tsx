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

interface ProgressEvent {
  step: string;
  status: string;
  detail: string;
  progress: number;
}

import { apiFetch, backendUrl } from "@/lib/api";
import { explainIntegrity } from "@/lib/scoreExplanation";
import { ScoreLabel } from "@/components/ui/score-explanation";

export default function ResearcherAnalysisPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [scopusId, setScopusId] = useState("");
  const [scholarId, setScholarId] = useState("");
  const [orcid, setOrcid] = useState("");
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [progress, setProgress] = useState(0);

  const hasInput = name || scopusId || scholarId || orcid;

  const handleSubmit = useCallback(async () => {
    if (!hasInput) return;
    setLoading(true);
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
        setLoading(false);
        return;
      }

      const data = await res.json();
      const profileId = data.id;

      // Start SSE stream
      const es = new EventSource(backendUrl(`/api/researcher/${profileId}/stream`));

      es.onmessage = (e) => {
        try {
          const event: ProgressEvent = JSON.parse(e.data);
          setEvents((prev) => [...prev, event]);
          setProgress(event.progress);

          if (event.status === "completed" || event.status === "failed") {
            es.close();
            setLoading(false);
            if (event.status === "completed") {
              router.push(`/researcher/${profileId}`);
            }
          }
        } catch {
          // ignore
        }
      };

      es.onerror = () => {
        es.close();
        setLoading(false);
        if (profileId) {
          router.push(`/researcher/${profileId}`);
        }
      };
    } catch {
      setLoading(false);
    }
  }, [name, scopusId, scholarId, orcid, hasInput, router]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Analyze Researcher</h1>

      <Card className="border-zinc-800 bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="text-lg text-white">Evaluate academic integrity</CardTitle>
          <p className="text-sm text-zinc-400">
            Search by name, Scopus ID, Google Scholar ID, or ORCID
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-zinc-400">Researcher Name</Label>
            <Input
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
              <Label className="text-zinc-400">Scopus ID</Label>
              <Input
                placeholder="e.g. 57203100718"
                value={scopusId}
                onChange={(e) => setScopusId(e.target.value)}
                disabled={loading}
                className="mt-1 border-zinc-700 bg-zinc-800 text-white placeholder:text-zinc-500"
              />
            </div>
            <div>
              <Label className="text-zinc-400">Google Scholar ID</Label>
              <Input
                placeholder="e.g. xJaxiEEAAAAJ"
                value={scholarId}
                onChange={(e) => setScholarId(e.target.value)}
                disabled={loading}
                className="mt-1 border-zinc-700 bg-zinc-800 text-white placeholder:text-zinc-500"
              />
            </div>
            <div>
              <Label className="text-zinc-400">ORCID</Label>
              <Input
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
        </CardContent>
      </Card>

      {/* Progress */}
      {loading && events.length > 0 && (
        <Card className="border-zinc-800 bg-zinc-900/50">
          <CardContent className="py-6">
            <div className="mb-4 h-2 w-full overflow-hidden rounded-full bg-zinc-800">
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
  const [analyses, setAnalyses] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    apiFetch("/api/researcher/")
      .then((r) => r.ok ? r.json() : { items: [] })
      .then((data) => setAnalyses(data.items || []))
      .catch(() => {})
      .finally(() => setLoaded(true));
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
          <div className="flex flex-col items-center py-8">
            <Users className="mb-3 h-10 w-10 text-zinc-600" />
            <p className="text-sm text-zinc-500">No researcher analyses yet.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {analyses.map((a: any) => (
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
                      <span className={`text-lg font-bold ${
                        a.integrity_score >= 70 ? "text-emerald-400"
                        : a.integrity_score >= 40 ? "text-amber-400"
                        : "text-red-400"
                      }`}>
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
