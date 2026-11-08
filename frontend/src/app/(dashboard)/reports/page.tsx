"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  Check,
  Download,
  ExternalLink,
  FileText,
  GitCompare,
  Loader2,
  NotebookPen,
  Plus,
  Share2,
  Users,
  X,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiFetch } from "@/lib/api";
import { toast } from "@/lib/toast";

interface ReportItem {
  id: string;
  report_type: string;
  template: string;
  title: string;
  summary: string | null;
  pdf_path: string | null;
  share_token: string;
  source_check_id: string | null;
  researcher_profile_id: string | null;
  source_check_ids: string[] | null;
  researcher_profile_ids: string[] | null;
  annotations: Array<{ text: string; author_name?: string; created_at?: string }> | null;
  created_at: string;
}

interface SourceCheckSummary {
  id: string;
  input_title: string | null;
  overall_credibility_score: number | null;
  created_at: string;
}

interface ResearcherSummary {
  id: string;
  researcher_name: string;
  institution: string | null;
}

const TEMPLATE_LABELS: Record<string, string> = {
  full: "Full",
  executive_summary: "Summary",
  comparison: "Comparison",
  institutional_audit: "Audit",
  scheduled_summary: "Scheduled",
};

export default function ReportsPage() {
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Compose dialog state — used for comparison + audit reports.
  const [composeOpen, setComposeOpen] = useState(false);
  const [composeMode, setComposeMode] = useState<"comparison" | "institutional_audit">("comparison");

  // Annotations dialog state.
  const [annotateReport, setAnnotateReport] = useState<ReportItem | null>(null);

  async function refresh() {
    try {
      const r = await apiFetch("/api/reports/");
      if (!r.ok) throw new Error("Failed to load reports");
      const data = await r.json();
      setReports(data.items || []);
    } catch {
      setError("Could not load reports. Please refresh the page.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  const copyShareLink = async (token: string, reportId: string) => {
    setError(null);
    if (!token) {
      setError("This report does not have a share link.");
      return;
    }
    const url = `${window.location.origin}/report/${token}`;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
        setCopiedId(reportId);
        setTimeout(() => setCopiedId(null), 2000);
        return;
      }
    } catch {
      /* fall through */
    }
    window.prompt("Copy this share link:", url);
  };

  const downloadReport = async (report: ReportItem) => {
    setError(null);
    setDownloadingId(report.id);
    try {
      const res = await apiFetch(`/api/reports/${report.id}/download`);
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "PDF download failed");
      }
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = `artiproof-report-${report.id.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF download failed");
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">Reports</h1>
          <p className="mt-1 text-sm text-zinc-700 dark:text-zinc-300">
            Download PDF reports, add notes, or copy a public share link.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            className="border-zinc-400 bg-white text-zinc-900 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800"
            onClick={() => {
              setComposeMode("comparison");
              setComposeOpen(true);
            }}
          >
            <GitCompare className="mr-1 h-4 w-4" />
            New comparison
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="border-zinc-400 bg-white text-zinc-900 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800"
            onClick={() => {
              setComposeMode("institutional_audit");
              setComposeOpen(true);
            }}
          >
            <Users className="mr-1 h-4 w-4" />
            New audit
          </Button>
        </div>
      </div>

      <Card className="border-zinc-200 bg-white text-zinc-900 shadow-xl shadow-black/5 dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-100 dark:shadow-black/20">
        <CardHeader>
          <CardTitle className="text-sm text-zinc-700 dark:text-zinc-400">Generated Reports</CardTitle>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="mb-4 flex items-start gap-2 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-brand dark:text-brand-fg" />
            </div>
          ) : reports.length === 0 ? (
            <div className="flex flex-col items-center py-12">
              <FileText className="mb-3 h-10 w-10 text-zinc-500" />
              <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">No reports generated yet.</p>
              <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
                Reports can be generated from source check or researcher analysis results.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {reports.map((report) => {
                const annotationCount = report.annotations?.length ?? 0;
                const templateLabel = TEMPLATE_LABELS[report.template] || report.template;
                return (
                  <div
                    key={report.id}
                    className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-800/30 dark:shadow-none"
                  >
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 shrink-0 text-brand dark:text-brand-fg" />
                          <p className="truncate text-sm font-semibold text-zinc-900 dark:text-white">{report.title}</p>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                          <Badge className={
                            report.report_type === "researcher_integrity" || report.report_type === "institutional_audit"
                              ? "bg-accent-amber/15 text-accent-amber"
                              : "bg-brand-soft text-brand dark:bg-brand/15 dark:text-brand-fg"
                          }>
                            {templateLabel}
                          </Badge>
                          {annotationCount > 0 && (
                            <Badge className="bg-zinc-200 text-zinc-700 dark:bg-zinc-700 dark:text-zinc-200">
                              {annotationCount} note{annotationCount === 1 ? "" : "s"}
                            </Badge>
                          )}
                          <span className="text-xs font-medium text-zinc-600 dark:text-zinc-400">
                            {new Date(report.created_at).toLocaleDateString()}
                          </span>
                        </div>
                        {report.summary && (
                          <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-zinc-700 dark:text-zinc-300">{report.summary}</p>
                        )}
                      </div>

                      <div className="flex shrink-0 flex-wrap gap-2 lg:justify-end">
                        <Button
                          variant="outline"
                          size="sm"
                          className="border-zinc-400 bg-white text-zinc-900 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800"
                          onClick={() => setAnnotateReport(report)}
                        >
                          <NotebookPen className="mr-1 h-3 w-3" />
                          Notes
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="border-zinc-400 bg-white text-zinc-900 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800"
                          onClick={() => copyShareLink(report.share_token, report.id)}
                        >
                          {copiedId === report.id ? (
                            <Check className="mr-1 h-3 w-3" />
                          ) : (
                            <Share2 className="mr-1 h-3 w-3" />
                          )}
                          {copiedId === report.id ? "Copied" : "Share"}
                        </Button>
                        <Button
                          size="sm"
                          className="bg-brand text-white hover:bg-brand-hover"
                          onClick={() => downloadReport(report)}
                          disabled={downloadingId === report.id}
                        >
                          {downloadingId === report.id ? (
                            <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                          ) : (
                            <Download className="mr-1 h-3 w-3" />
                          )}
                          PDF
                        </Button>
                        {report.source_check_id && (
                          <a href={`/check/${report.source_check_id}`} aria-label="Open source check">
                            <Button variant="outline" size="sm" className="border-zinc-400 bg-white text-zinc-900 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800">
                              <ExternalLink className="h-3 w-3" />
                            </Button>
                          </a>
                        )}
                        {report.researcher_profile_id && (
                          <a href={`/researcher/${report.researcher_profile_id}`} aria-label="Open researcher profile">
                            <Button variant="outline" size="sm" className="border-zinc-400 bg-white text-zinc-900 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800">
                              <ExternalLink className="h-3 w-3" />
                            </Button>
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <ComposeDialog
        open={composeOpen}
        mode={composeMode}
        onClose={() => setComposeOpen(false)}
        onCreated={() => {
          setComposeOpen(false);
          refresh();
        }}
      />

      <AnnotationsDialog
        report={annotateReport}
        onClose={() => setAnnotateReport(null)}
        onSaved={(updated) => {
          setReports((rs) => rs.map((r) => (r.id === updated.id ? updated : r)));
          setAnnotateReport(null);
        }}
      />
    </div>
  );
}

// ─── Compose comparison / audit ──────────────────────────────────────────

function ComposeDialog({
  open,
  mode,
  onClose,
  onCreated,
}: {
  open: boolean;
  mode: "comparison" | "institutional_audit";
  onClose: () => void;
  onCreated: () => void;
}) {
  const [items, setItems] = useState<Array<SourceCheckSummary | ResearcherSummary>>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isComparison = mode === "comparison";
  const minSelected = 2;
  const maxSelected = isComparison ? 10 : 25;

  useEffect(() => {
    if (!open) return;
    setError(null);
    setSelected(new Set());
    setLoading(true);
    (async () => {
      try {
        const url = isComparison
          ? "/api/source-check/?page_size=50"
          : "/api/researcher/?page_size=50";
        const res = await apiFetch(url);
        if (!res.ok) throw new Error("load failed");
        const data = await res.json();
        setItems(data.items || []);
      } catch {
        setError("Could not load list. Try again.");
      } finally {
        setLoading(false);
      }
    })();
  }, [open, isComparison]);

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else if (next.size < maxSelected) {
        next.add(id);
      }
      return next;
    });
  }

  async function submit() {
    setError(null);
    if (selected.size < minSelected) {
      setError(`Pick at least ${minSelected}`);
      return;
    }
    setSubmitting(true);
    try {
      const body = isComparison
        ? { template: "comparison", source_check_ids: Array.from(selected) }
        : { template: "institutional_audit", researcher_profile_ids: Array.from(selected) };
      const res = await apiFetch("/api/reports/generate", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(data.detail || "Failed to generate report");
      }
      toast.success("Report generated");
      onCreated();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to generate";
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[80vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isComparison ? "New comparison report" : "New institutional audit"}
          </DialogTitle>
          <DialogDescription>
            {isComparison
              ? `Pick ${minSelected}–${maxSelected} source checks to compare side-by-side.`
              : `Pick ${minSelected}–${maxSelected} researchers for the audit summary.`}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-brand" />
          </div>
        ) : items.length === 0 ? (
          <p className="py-8 text-center text-sm text-zinc-600 dark:text-zinc-400">
            {isComparison
              ? "No source checks yet. Run some first."
              : "No researcher profiles yet. Analyze some first."}
          </p>
        ) : (
          <ul className="max-h-80 space-y-1 overflow-y-auto">
            {items.map((item) => {
              const id = item.id;
              const isSelected = selected.has(id);
              const title = isComparison
                ? (item as SourceCheckSummary).input_title || "Untitled"
                : (item as ResearcherSummary).researcher_name;
              const sub = isComparison
                ? `Score ${(item as SourceCheckSummary).overall_credibility_score?.toFixed(0) ?? "—"}`
                : (item as ResearcherSummary).institution || "—";
              return (
                <li key={id}>
                  <button
                    type="button"
                    onClick={() => toggle(id)}
                    className={
                      "flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors " +
                      (isSelected
                        ? "border-brand bg-brand-soft dark:border-brand-fg dark:bg-brand/10"
                        : "border-zinc-200 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800/40")
                    }
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-zinc-900 dark:text-zinc-100">{title}</p>
                      <p className="truncate text-xs text-zinc-600 dark:text-zinc-400">{sub}</p>
                    </div>
                    {isSelected && <Check className="h-4 w-4 text-brand dark:text-brand-fg" />}
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        <DialogFooter>
          <span className="mr-auto text-xs text-zinc-600 dark:text-zinc-400">
            {selected.size} / {maxSelected} selected
          </span>
          <DialogClose render={<Button variant="outline" size="sm">Cancel</Button>} />
          <Button
            size="sm"
            className="bg-brand text-white hover:bg-brand-hover"
            disabled={submitting || selected.size < minSelected}
            onClick={submit}
          >
            {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Generate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Annotations editor ─────────────────────────────────────────────────

function AnnotationsDialog({
  report,
  onClose,
  onSaved,
}: {
  report: ReportItem | null;
  onClose: () => void;
  onSaved: (updated: ReportItem) => void;
}) {
  const [drafts, setDrafts] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!report) return;
    setError(null);
    setDrafts(
      report.annotations && report.annotations.length > 0
        ? report.annotations.map((a) => a.text)
        : [""]
    );
  }, [report]);

  async function save() {
    if (!report) return;
    const cleaned = drafts.map((d) => d.trim()).filter((d) => d.length > 0);
    setError(null);
    setSaving(true);
    try {
      const res = await apiFetch(`/api/reports/${report.id}/annotations`, {
        method: "PUT",
        body: JSON.stringify({
          annotations: cleaned.map((text) => ({ text })),
        }),
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(data.detail || "Failed to save");
      }
      const updated = (await res.json()) as ReportItem;
      toast.success("Notes saved");
      onSaved(updated);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to save";
      setError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  const open = report !== null;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Notes</DialogTitle>
          <DialogDescription>
            Notes appear at the top of the PDF when shared or downloaded.
          </DialogDescription>
        </DialogHeader>
        {error && (
          <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
            {error}
          </div>
        )}
        <div className="space-y-3">
          {drafts.map((text, i) => (
            <div key={i} className="flex gap-2">
              <textarea
                value={text}
                onChange={(e) =>
                  setDrafts((d) => d.map((t, j) => (j === i ? e.target.value : t)))
                }
                rows={3}
                placeholder="Add a note for the reader…"
                className="flex-1 rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-brand/40 dark:border-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-100"
              />
              {drafts.length > 1 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setDrafts((d) => d.filter((_, j) => j !== i))}
                  aria-label="Remove note"
                  className="self-start"
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
          ))}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setDrafts((d) => [...d, ""])}
            disabled={drafts.length >= 50}
          >
            <Plus className="mr-1 h-3 w-3" />
            Add note
          </Button>
        </div>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" size="sm">Cancel</Button>} />
          <Button
            size="sm"
            className="bg-brand text-white hover:bg-brand-hover"
            disabled={saving}
            onClick={save}
          >
            {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
