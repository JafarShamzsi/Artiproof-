"use client";

import { use, useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AlertCircle, Download, FileText, Loader2, Shield } from "lucide-react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

interface SharedReport {
  id: string;
  report_type: string;
  title: string;
  summary: string | null;
  created_at: string;
}

export default function SharedReportPage({
  params,
}: {
  params: Promise<{ shareToken: string }>;
}) {
  const { shareToken } = use(params);
  const [report, setReport] = useState<SharedReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    fetch(`${BACKEND_URL}/api/reports/shared/${shareToken}`)
      .then((r) => {
        if (!r.ok) throw new Error("Not found");
        return r.json();
      })
      .then(setReport)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [shareToken]);

  const downloadReport = async () => {
    if (!report) return;
    setDownloadError(null);
    setDownloading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/api/reports/${report.id}/download`);
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
      setDownloadError(err instanceof Error ? err.message : "PDF download failed");
    } finally {
      setDownloading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950">
        <Loader2 className="h-8 w-8 animate-spin text-emerald-300" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950 p-4">
        <Card className="w-full max-w-lg border-white bg-white text-zinc-950">
          <CardContent className="py-12 text-center">
            <Shield className="mx-auto mb-4 h-12 w-12 text-zinc-500" />
            <h1 className="text-xl font-bold text-zinc-950">Report Not Found</h1>
            <p className="mt-2 text-sm text-zinc-700">
              This shared report link may have expired or does not exist.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 p-4 md:p-8">
      <div className="mx-auto max-w-3xl">
        {/* Header */}
        <div className="mb-6 flex items-center justify-center gap-2">
          <Shield className="h-6 w-6 text-emerald-300" />
          <span className="text-lg font-bold text-white">ArtiProof</span>
        </div>

        <Card className="border-white bg-white text-zinc-950 shadow-xl shadow-black/20">
          <CardContent className="py-8">
            <div className="text-center">
              <FileText className="mx-auto mb-3 h-10 w-10 text-emerald-700" />
              <h1 className="text-2xl font-bold text-zinc-950">{report.title}</h1>
              <div className="mt-2 flex items-center justify-center gap-2">
                <Badge className={
                  report.report_type === "source_verification"
                    ? "bg-emerald-100 text-emerald-800"
                    : "bg-indigo-100 text-indigo-800"
                }>
                  {report.report_type === "source_verification" ? "Source Verification" : "Researcher Integrity"}
                </Badge>
                <span className="text-xs font-medium text-zinc-600">
                  {new Date(report.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>

            {report.summary && (
              <div className="mt-8">
                <h2 className="mb-3 text-sm font-semibold text-zinc-800">Executive Summary</h2>
                <div className="space-y-3">
                  {report.summary.split("\n\n").map((para, i) => (
                    para.trim() && (
                      <p key={i} className="text-sm leading-relaxed text-zinc-700">
                        {para}
                      </p>
                    )
                  ))}
                </div>
              </div>
            )}

            <div className="mt-8 flex flex-col items-center gap-3 text-center">
              {downloadError && (
                <div className="flex items-start gap-2 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{downloadError}</span>
                </div>
              )}

              <Button
                className="bg-emerald-600 text-white hover:bg-emerald-700"
                onClick={downloadReport}
                disabled={downloading}
              >
                {downloading ? (
                  <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                ) : (
                  <Download className="mr-1 h-4 w-4" />
                )}
                Download PDF
              </Button>

              <p className="text-xs text-zinc-600">
                This report was generated by ArtiProof Research Integrity Platform
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
