"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { AlertTriangle, Loader2, Shield } from "lucide-react";

import {
  FullWidthView,
  type FullWidthSourceCheckData,
} from "@/components/source-check/FullWidthView";
import type { SharedSourceCheck } from "@/types/api";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function SharedSourceCheckPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = use(params);
  const [data, setData] = useState<SharedSourceCheck | null>(null);
  const [loading, setLoading] = useState(true);
  // Distinguish "not found" (404) from "request errored" — only the former
  // gets the friendly "shared link is no longer available" message.
  const [notFound, setNotFound] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const ctl = new AbortController();
    (async () => {
      try {
        // Plain fetch — `apiFetch` would attach a Bearer token (irrelevant
        // here) and force-signOut on 401, which isn't possible from a public
        // route anyway, but better to keep this code path explicit.
        const res = await fetch(
          `${BACKEND_URL}/api/source-check/shared/${encodeURIComponent(token)}`,
          { signal: ctl.signal },
        );
        if (res.status === 404) {
          setNotFound(true);
          return;
        }
        if (!res.ok) {
          setErrorMessage(`Could not load shared check (HTTP ${res.status})`);
          return;
        }
        const body = (await res.json()) as SharedSourceCheck;
        setData(body);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setErrorMessage(e instanceof Error ? e.message : "Network error");
      } finally {
        setLoading(false);
      }
    })();
    return () => ctl.abort();
  }, [token]);

  if (loading) {
    return (
      <PublicShell>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-brand dark:text-brand-fg" />
        </div>
      </PublicShell>
    );
  }

  if (notFound) {
    return (
      <PublicShell>
        <Card className="mx-auto mt-12 max-w-md border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardContent className="py-12 text-center">
            <Shield className="mx-auto mb-3 h-10 w-10 text-zinc-400" />
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-white">
              This shared link is no longer available
            </h2>
            <p className="mt-2 text-sm text-zinc-500">
              The owner may have revoked the link, or the original check has been deleted.
            </p>
            <div className="mt-6">
              <Link
                href="/"
                className="inline-flex h-9 items-center rounded-lg bg-brand px-4 text-sm font-medium text-white hover:bg-brand-hover"
              >
                Go to ArtiProof
              </Link>
            </div>
          </CardContent>
        </Card>
      </PublicShell>
    );
  }

  if (errorMessage || !data) {
    return (
      <PublicShell>
        <Card className="mx-auto mt-12 max-w-md border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardContent className="py-12 text-center">
            <AlertTriangle className="mx-auto mb-3 h-10 w-10 text-red-600 dark:text-red-400" />
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-white">
              Couldn&apos;t load this shared check
            </h2>
            <p className="mt-2 text-sm text-zinc-500">
              {errorMessage || "Unknown error."}
            </p>
          </CardContent>
        </Card>
      </PublicShell>
    );
  }

  // The public payload omits `input_content` for url-type checks (the URL is
  // the secret). FullWidthView already guards that field, so no explicit
  // shimming is needed here.
  const viewData: FullWidthSourceCheckData = {
    id: data.id,
    input_type: data.input_type,
    input_title: data.input_title,
    status: data.status,
    overall_credibility_score: data.overall_credibility_score,
    ai_content_percentage: data.ai_content_percentage,
    misinfo_claims_found: data.misinfo_claims_found,
    has_pdf: data.has_pdf,
    has_annotated_pdf: data.has_annotated_pdf,
    created_at: data.created_at,
    completed_at: data.completed_at,
    claims: data.claims,
    ai_detections: data.ai_detections,
    citations: data.citations,
    score_breakdown: data.score_breakdown,
    // Public payload intentionally omits input_content / model_metadata.
  };

  return (
    <PublicShell>
      <FullWidthView
        data={viewData}
        readOnly
        backHref="/"
        banner={
          <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-400">
            Shared by an ArtiProof user · Read-only public view of{" "}
            <span className="font-medium text-zinc-900 dark:text-zinc-200">
              {data.input_title || data.input_type.toUpperCase()}
            </span>
          </div>
        }
      />
      <div className="mx-auto mt-10 max-w-3xl border-t border-zinc-200 pt-6 text-center text-xs text-zinc-500 dark:border-zinc-800">
        This is a read-only shared view. Generate your own at{" "}
        <Link
          href="/"
          className="font-medium text-brand hover:underline dark:text-brand-fg"
        >
          artiproof.com
        </Link>
        .
      </div>
    </PublicShell>
  );
}

// Lightweight chrome (header strip + container) — separate from the dashboard
// shell so the shared view stays anonymous-friendly.
function PublicShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-[100dvh] bg-zinc-50 dark:bg-zinc-950">
      <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/80 backdrop-blur-xl dark:border-zinc-800 dark:bg-zinc-950/80">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand">
              <Shield className="h-3.5 w-3.5 text-white" />
            </div>
            <span className="text-base font-bold text-zinc-900 dark:text-white">
              ArtiProof
            </span>
          </Link>
          <Link
            href="/"
            className="text-xs text-zinc-500 hover:text-zinc-900 dark:hover:text-white"
          >
            Verify your own source →
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
    </div>
  );
}
