"use client";

import { useCallback, useState } from "react";
import { apiFetch, backendUrl } from "./api";

type Opts =
  | { sourceCheckId: string; researcherProfileId?: undefined }
  | { sourceCheckId?: undefined; researcherProfileId: string };

interface GeneratedReport {
  id: string;
  share_token: string;
}

/**
 * Hook that powers the "Share" and "Report" buttons on source-check and
 * researcher detail pages. First click generates the report via
 * `POST /api/reports/generate` and caches the result in component state;
 * subsequent clicks reuse it.
 */
export function useReportActions(opts: Opts) {
  const [report, setReport] = useState<GeneratedReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ensureReport = useCallback(async (): Promise<GeneratedReport | null> => {
    if (report) return report;
    setBusy(true);
    setError(null);
    try {
      const body = opts.sourceCheckId
        ? { source_check_id: opts.sourceCheckId }
        : { researcher_profile_id: opts.researcherProfileId };
      const res = await apiFetch("/api/reports/generate", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Failed to generate report");
        return null;
      }
      const r = (await res.json()) as GeneratedReport;
      setReport(r);
      return r;
    } catch {
      setError("Network error — please try again");
      return null;
    } finally {
      setBusy(false);
    }
  }, [report, opts.sourceCheckId, opts.researcherProfileId]);

  const share = useCallback(async () => {
    const r = await ensureReport();
    if (!r) return;
    const url = `${window.location.origin}/report/${r.share_token}`;

    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
        return;
      }
    } catch {
      // fall through
    }

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
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt("Copy this share link:", url);
    }
  }, [ensureReport]);

  const download = useCallback(async () => {
    const r = await ensureReport();
    if (!r) return;
    window.open(
      backendUrl(`/api/reports/${r.id}/download`),
      "_blank",
      "noopener,noreferrer"
    );
  }, [ensureReport]);

  return { share, download, busy, copied, error };
}
