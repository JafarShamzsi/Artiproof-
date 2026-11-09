"use client";

import { Suspense, use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  Clock,
  Loader2,
  XCircle,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { scoreColor } from "@/lib/colors";
import type { SourceCheckListItem } from "@/types/api";

const POLL_INTERVAL_MS = 2000;

function isTerminal(status: string) {
  return status === "completed" || status === "failed";
}

export default function BulkBatchPage({
  params,
}: {
  params: Promise<{ batchId: string }>;
}) {
  const { batchId } = use(params);
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-brand dark:text-brand-fg" />
        </div>
      }
    >
      <BulkBatchInner batchId={batchId} />
    </Suspense>
  );
}

function BulkBatchInner({ batchId }: { batchId: string }) {
  const searchParams = useSearchParams();
  const idsParam = searchParams.get("ids") ?? "";

  // Frozen on first render — `searchParams` returns a new object reference per
  // render, but the ids list itself is immutable for a given batch, so we
  // memo on the raw string.
  const ids = useMemo(
    () =>
      idsParam
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    [idsParam],
  );

  const [items, setItems] = useState<SourceCheckListItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [pollError, setPollError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Single fetch helper — used both for initial load and the polling tick.
  const fetchBatch = useCallback(async (signal?: AbortSignal) => {
    if (ids.length === 0) {
      setLoaded(true);
      return;
    }
    try {
      const res = await apiFetch(
        `/api/source-check/batch?ids=${encodeURIComponent(ids.join(","))}`,
        { signal },
      );
      if (!res.ok) {
        setPollError(`Failed to load batch (HTTP ${res.status})`);
        return;
      }
      const next = (await res.json()) as SourceCheckListItem[];
      setItems(next);
      setPollError(null);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setPollError(e instanceof Error ? e.message : "Network error");
    } finally {
      setLoaded(true);
    }
  }, [ids]);

  // Initial fetch on mount.
  useEffect(() => {
    const ctl = new AbortController();
    fetchBatch(ctl.signal);
    return () => ctl.abort();
  }, [fetchBatch]);

  // Poll while any item is still pending or processing. We only start the
  // interval when there's pending work, and clear it the moment everything
  // settles, so we never hold a needless timer open.
  const allTerminal = items.length > 0 && items.every((i) => isTerminal(i.status));

  useEffect(() => {
    // Wait for the initial fetch to land before deciding whether to poll —
    // otherwise allTerminal is briefly true (zero items) and we'd skip
    // polling for the just-submitted batch.
    if (!loaded || ids.length === 0) return;
    if (allTerminal) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }
    if (intervalRef.current) return; // already polling
    intervalRef.current = setInterval(() => {
      fetchBatch();
    }, POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [allTerminal, fetchBatch, ids.length, loaded]);

  const completedCount = items.filter((i) => i.status === "completed").length;
  const failedCount = items.filter((i) => i.status === "failed").length;
  const finishedCount = completedCount + failedCount;
  const total = items.length || ids.length;
  const progressPct = total > 0 ? (finishedCount / total) * 100 : 0;

  // Empty state for stale URLs (someone re-opened the page after the batch
  // was discarded, or they hit it without `ids=`).
  if (ids.length === 0) {
    return (
      <div className="space-y-4">
        <Link
          href="/check"
          className="flex items-center gap-1 text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Source Checks
        </Link>
        <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardContent className="py-12 text-center text-sm text-zinc-500">
            No batch ids supplied. Start a bulk run from the{" "}
            <Link href="/check" className="text-brand hover:underline">
              Check page
            </Link>
            .
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/check"
            aria-label="Back to source checks"
            className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <h1 className="font-display text-2xl font-bold text-zinc-900 dark:text-white">
            Bulk Source Check
          </h1>
          <Badge className="bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
            #{batchId}
          </Badge>
        </div>
        {allTerminal && (
          <Link
            href="/check"
            className="inline-flex h-9 items-center rounded-lg bg-brand px-4 text-sm font-medium text-white hover:bg-brand-hover"
          >
            Done <ArrowRight className="ml-1.5 h-4 w-4" />
          </Link>
        )}
      </div>

      {/* Progress header */}
      <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="flex items-center justify-between text-sm">
            <span className="text-zinc-700 dark:text-zinc-300">
              {finishedCount} of {total} complete
              {failedCount > 0 && (
                <span className="ml-2 text-red-700 dark:text-red-400">
                  ({failedCount} failed)
                </span>
              )}
            </span>
            <span className="text-xs text-zinc-500">
              {allTerminal
                ? "All done"
                : "Updating every 2 seconds…"}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div
            role="progressbar"
            aria-label="Batch progress"
            aria-valuenow={Math.round(progressPct)}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-2 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800"
          >
            <div
              className="h-full rounded-full bg-brand transition-all duration-300"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          {pollError && (
            <p
              role="alert"
              className="mt-3 flex items-center gap-2 text-xs text-red-700 dark:text-red-400"
            >
              <AlertTriangle className="h-3.5 w-3.5" />
              {pollError}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Item list */}
      <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="text-sm text-zinc-600 dark:text-zinc-400">
            Items
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!loaded ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-brand dark:text-brand-fg" />
            </div>
          ) : items.length === 0 ? (
            <p className="py-6 text-center text-sm text-zinc-500">
              No checks found for this batch. They may have been deleted or
              belong to another account.
            </p>
          ) : (
            <ul className="space-y-2">
              {items.map((item) => (
                <BatchRow key={item.id} item={item} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function BatchRow({ item }: { item: SourceCheckListItem }) {
  const isCompleted = item.status === "completed";
  const isFailed = item.status === "failed";
  const StatusIcon = isCompleted
    ? CheckCircle
    : isFailed
      ? XCircle
      : item.status === "processing"
        ? Loader2
        : Clock;

  return (
    <li className="flex items-center justify-between gap-3 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-800/30">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <StatusIcon
          aria-hidden="true"
          className={
            "h-4 w-4 shrink-0 " +
            (isCompleted
              ? "text-emerald-700 dark:text-emerald-400"
              : isFailed
                ? "text-red-700 dark:text-red-400"
                : item.status === "processing"
                  ? "animate-spin text-blue-700 dark:text-blue-400"
                  : "text-zinc-500")
          }
        />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-zinc-900 dark:text-white">
            {item.input_title || item.input_type.toUpperCase()}
          </p>
          <p className="text-xs text-zinc-500">
            {new Date(item.created_at).toLocaleString()}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Badge
          className={
            isCompleted
              ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-400"
              : isFailed
                ? "bg-red-500/20 text-red-700 dark:text-red-400"
                : "bg-blue-500/20 text-blue-700 dark:text-blue-400"
          }
        >
          {item.status}
        </Badge>
        {item.overall_credibility_score !== null && (
          <span
            className={`text-base font-bold ${scoreColor(item.overall_credibility_score)}`}
          >
            {Math.round(item.overall_credibility_score)}
          </span>
        )}
        {isCompleted && (
          <Link
            href={`/check/${item.id}`}
            className="text-xs text-brand hover:underline dark:text-brand-fg"
          >
            View
          </Link>
        )}
      </div>
    </li>
  );
}
