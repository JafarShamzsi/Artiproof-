"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FileText, Download, Share2, Loader2, ExternalLink } from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

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

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/reports/`)
      .then((r) => r.ok ? r.json() : { items: [] })
      .then((data) => setReports(data.items || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const copyShareLink = (token: string, reportId: string) => {
    const url = `${window.location.origin}/report/${token}`;
    navigator.clipboard.writeText(url);
    setCopiedId(reportId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Reports</h1>

      <Card className="border-zinc-800 bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="text-sm text-zinc-400">Generated Reports</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-zinc-500" />
            </div>
          ) : reports.length === 0 ? (
            <div className="flex flex-col items-center py-12">
              <FileText className="mb-3 h-10 w-10 text-zinc-600" />
              <p className="text-sm text-zinc-500">No reports generated yet.</p>
              <p className="mt-1 text-xs text-zinc-600">
                Reports can be generated from source check or researcher analysis results.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {reports.map((report) => (
                <div
                  key={report.id}
                  className="rounded-lg border border-zinc-800 bg-zinc-800/30 px-4 py-4"
                >
                  <div className="flex items-start justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 shrink-0 text-zinc-400" />
                        <p className="truncate text-sm font-medium text-white">{report.title}</p>
                      </div>
                      <div className="mt-1 flex items-center gap-2">
                        <Badge className={
                          report.report_type === "source_verification"
                            ? "bg-emerald-500/20 text-emerald-400"
                            : "bg-purple-500/20 text-purple-400"
                        }>
                          {report.report_type === "source_verification" ? "Source Verification" : "Researcher Integrity"}
                        </Badge>
                        <span className="text-xs text-zinc-500">
                          {new Date(report.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      {report.summary && (
                        <p className="mt-2 text-xs text-zinc-400 line-clamp-2">{report.summary}</p>
                      )}
                    </div>

                    <div className="ml-4 flex shrink-0 gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-zinc-700 text-zinc-400"
                        onClick={() => copyShareLink(report.share_token, report.id)}
                      >
                        <Share2 className="mr-1 h-3 w-3" />
                        {copiedId === report.id ? "Copied!" : "Share"}
                      </Button>

                      {report.pdf_path && (
                        <a href={`${BACKEND_URL}/api/reports/${report.id}/download`}>
                          <Button size="sm" className="bg-emerald-500 text-white hover:bg-emerald-600">
                            <Download className="mr-1 h-3 w-3" /> PDF
                          </Button>
                        </a>
                      )}

                      {report.source_check_id && (
                        <a href={`/check/${report.source_check_id}`}>
                          <Button variant="outline" size="sm" className="border-zinc-700 text-zinc-400">
                            <ExternalLink className="h-3 w-3" />
                          </Button>
                        </a>
                      )}
                      {report.researcher_profile_id && (
                        <a href={`/researcher/${report.researcher_profile_id}`}>
                          <Button variant="outline" size="sm" className="border-zinc-700 text-zinc-400">
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
