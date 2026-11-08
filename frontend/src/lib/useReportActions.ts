"use client";

import { useCallback, useState } from "react";
import { apiFetch } from "./api";
import { toast } from "./toast";

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
        const msg = data.detail || "Failed to generate report";
        setError(msg);
        toast.error(msg);
        return null;
      }
      const r = (await res.json()) as GeneratedReport;
      setReport(r);
      return r;
    } catch {
      const msg = "Network error — please try again";
      setError(msg);
      toast.error(msg);
      return null;
    } finally {
      setBusy(false);
    }
  }, [report, opts.sourceCheckId, opts.researcherProfileId]);

  const share = useCallback(async () => {
    const r = await ensureReport();
    if (!r) return;
    const url = `${window.location.origin}/report/${r.share_token}`;

    // Inline `Copied!` text on the button gives instant visual confirmation;
    // the toast covers accessibility (screen-reader announcement) and people
    // who clicked away before the button settled.
    function announce() {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast.success("Link copied to clipboard");
    }

    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
        announce();
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
      announce();
    } catch {
      window.prompt("Copy this share link:", url);
    }
  }, [ensureReport]);

  const download = useCallback(async () => {
    const r = await ensureReport();
    if (!r) return;
    setError(null);
    setBusy(true);
    try {
      const res = await apiFetch(`/api/reports/${r.id}/download`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const msg = data.detail || `PDF download failed (HTTP ${res.status})`;
        setError(msg);
        toast.error(msg);
        return;
      }
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = `artiproof-report-${r.id.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objectUrl);
    } catch {
      const msg = "Network error during download";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }, [ensureReport]);

  return { share, download, busy, copied, error };
}
