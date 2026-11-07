"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertCircle,
  Check,
  Download,
  ExternalLink,
  FileText,
  Loader2,
  Share2,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface ReportItem {
  id: string;
  report_type: string;
  title: string;
  summary: string | null;
  pdf_path: string | null;
  share_token: string;
  source_check_id: string | null;
  researcher_profile_id: string | null;
  created_at: string;
}

export default function ReportsPage() {
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/api/reports/")
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load reports");
        return r.json();
      })
      .then((data) => setReports(data.items || []))
      .catch(() => setError("Could not load reports. Please refresh the page."))
      .finally(() => setLoading(false));
  }, []);

  const copyShareLink = async (token: string, reportId: string) => {
    setError(null);
    if (!token) {
      setError("This report does not have a share link. Regenerate the report and try again.");
      return;
    }

    const url = `${window.location.origin}/report/${token}`;

    // Modern path — requires secure context.
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
        setCopiedId(reportId);
        setTimeout(() => setCopiedId(null), 2000);
        return;
      }
    } catch {
      // fall through to textarea fallback
    }

    // Fallback for older browsers / non-secure contexts.
    try {
      const ta = document.createElement("textarea");
      ta.value = url;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopiedId(reportId);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // Last resort — show the user the URL so they can copy manually.
      window.prompt("Copy this share link:", url);
    }
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
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">Reports</h1>
        <p className="mt-1 text-sm text-zinc-700 dark:text-zinc-300">
          Download PDF reports or copy a public share link.
        </p>
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
              {reports.map((report) => (
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
                      <div className="mt-1 flex items-center gap-2">
                        <Badge className={
                          report.report_type === "source_verification"
                            ? "bg-brand-soft text-brand dark:bg-brand/15 dark:text-brand-fg"
                            : "bg-accent-amber/15 text-accent-amber"
                        }>
                          {report.report_type === "source_verification" ? "Source Verification" : "Researcher Integrity"}
                        </Badge>
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
                        <a href={`/check/${report.source_check_id}`}>
                          <Button variant="outline" size="sm" className="border-zinc-400 bg-white text-zinc-900 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800">
                            <ExternalLink className="h-3 w-3" />
                          </Button>
                        </a>
                      )}
                      {report.researcher_profile_id && (
                        <a href={`/researcher/${report.researcher_profile_id}`}>
                          <Button variant="outline" size="sm" className="border-zinc-400 bg-white text-zinc-900 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800">
                            <ExternalLink className="h-3 w-3" />
                          </Button>
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
