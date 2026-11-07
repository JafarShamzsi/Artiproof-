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

interface ProgressEvent {
  step: string;
  status: string;
  detail: string;
  progress: number;
}

export default function CheckSourcePage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState("url");
  const [inputValue, setInputValue] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [progress, setProgress] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const startSSE = useCallback((checkId: string) => {
    const es = new EventSource(backendUrl(`/api/source-check/${checkId}/stream`));

    es.onmessage = (e) => {
      try {
        const event: ProgressEvent = JSON.parse(e.data);
        setEvents((prev) => [...prev, event]);
        setProgress(event.progress);

        if (event.status === "completed" || event.status === "failed") {
          es.close();
          setLoading(false);
          if (event.status === "completed") {
            router.push(`/check/${checkId}`);
          }
        }
      } catch {
        // ignore
      }
    };

    es.onerror = () => {
      es.close();
      setLoading(false);
      router.push(`/check/${checkId}`);
    };
  }, [router]);

  const handleSubmit = useCallback(async () => {
    if (activeTab === "document") {
      // PDF upload flow
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
          setEvents([{ step: "error", status: "failed", detail: err.detail || "Upload failed", progress: 0 }]);
          setLoading(false);
          return;
        }

        const data = await res.json();
        startSSE(data.id);
      } catch {
        setLoading(false);
      }
    } else {
      // URL or text flow
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
          setLoading(false);
          return;
        }

        const data = await res.json();
        startSSE(data.id);
      } catch {
        setLoading(false);
      }
    }
  }, [inputValue, activeTab, selectedFile, startSSE]);

  const canSubmit =
    activeTab === "document" ? !!selectedFile : !!inputValue.trim();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Check Source</h1>

      <Card className="border-zinc-800 bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="text-lg text-white">
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
            <TabsList className="mb-4 bg-zinc-800">
              <TabsTrigger
                value="url"
                className="data-[state=active]:bg-emerald-500/20 data-[state=active]:text-emerald-400"
              >
                <Link2 className="mr-2 h-4 w-4" /> Paste URL
              </TabsTrigger>
              <TabsTrigger
                value="text"
                className="data-[state=active]:bg-emerald-500/20 data-[state=active]:text-emerald-400"
              >
                <FileText className="mr-2 h-4 w-4" /> Paste Text
              </TabsTrigger>
              <TabsTrigger
                value="document"
                className="data-[state=active]:bg-emerald-500/20 data-[state=active]:text-emerald-400"
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
                className="border-zinc-700 bg-zinc-800 text-white placeholder:text-zinc-500"
                disabled={loading}
              />
            </TabsContent>

            <TabsContent value="text">
              <Textarea
                placeholder="Paste the article text here..."
                value={activeTab === "text" ? inputValue : ""}
                onChange={(e) => setInputValue(e.target.value)}
                className="min-h-[200px] border-zinc-700 bg-zinc-800 text-white placeholder:text-zinc-500"
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
                <div className="flex items-center gap-3 rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3">
                  <FileIcon className="h-8 w-8 shrink-0 text-red-400" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-white">
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
                    className="h-8 w-8 p-0 text-zinc-400 hover:text-white"
                    disabled={loading}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex w-full flex-col items-center justify-center rounded-lg border-2 border-dashed border-zinc-700 py-12 transition hover:border-emerald-500/50"
                  disabled={loading}
                >
                  <Upload className="mb-3 h-8 w-8 text-zinc-500" />
                  <p className="text-sm text-zinc-400">
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
            className="mt-4 w-full bg-emerald-500 text-white hover:bg-emerald-600"
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
        </CardContent>
      </Card>

      {/* Progress */}
      {loading && events.length > 0 && (
        <Card className="border-zinc-800 bg-zinc-900/50">
          <CardContent className="py-6">
            <div className="mb-4 h-2 w-full overflow-hidden rounded-full bg-zinc-800">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all duration-300"
                style={{ width: `${progress * 100}%` }}
              />
            </div>
            <div className="space-y-2">
              {events.map((event, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  {event.status === "done" ? (
                    <CheckCircle className="h-4 w-4 shrink-0 text-emerald-400" />
                  ) : event.status === "error" || event.status === "warning" ? (
                    <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
                  ) : event.status === "processing" ? (
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin text-blue-400" />
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

      {/* Past Checks */}
      {!loading && <PastChecks />}
    </div>
  );
}

function PastChecks() {
  const [checks, setChecks] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    apiFetch("/api/source-check/")
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((data) => setChecks(data.items || []))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  const verdictColor = (score: number | null) => {
    if (score === null) return "text-zinc-400";
    if (score >= 70) return "text-emerald-400";
    if (score >= 40) return "text-amber-400";
    return "text-red-400";
  };

  return (
    <Card className="border-zinc-800 bg-zinc-900/50">
      <CardHeader>
        <CardTitle className="text-sm text-zinc-400">
          Past Source Checks
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!loaded ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-zinc-500" />
          </div>
        ) : checks.length === 0 ? (
          <div className="flex flex-col items-center py-8">
            <Shield className="mb-3 h-10 w-10 text-zinc-600" />
            <p className="text-sm text-zinc-500">No source checks yet.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {checks.map((check: any) => (
              <a
                key={check.id}
                href={`/check/${check.id}`}
                className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-800/30 px-4 py-3 transition hover:border-zinc-700"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-white">
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
                        ? "bg-emerald-500/20 text-emerald-400"
                        : check.status === "failed"
                          ? "bg-red-500/20 text-red-400"
                          : "bg-blue-500/20 text-blue-400"
                    }
                  >
                    {check.status}
                  </Badge>
                  {check.overall_credibility_score !== null && (
                    <span
                      className={`text-lg font-bold ${verdictColor(check.overall_credibility_score)}`}
                    >
                      {Math.round(check.overall_credibility_score)}
                    </span>
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
