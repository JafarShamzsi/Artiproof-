"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Eye,
  Loader2,
  Minus,
  Trash2,
} from "lucide-react";

import { apiFetch } from "@/lib/api";
import { toast } from "@/lib/toast";
import { scoreColor } from "@/lib/colors";
import { EmptyState } from "@/components/ui/empty-state";
import { ListSkeleton } from "@/components/ui/skeleton";
import type { WatchlistEntry } from "@/types/api";

// Mirrors backend MAX_WATCHLIST so the chrome doesn't drift if the cap moves.
const WATCHLIST_CAP = 50;

export default function WatchlistPage() {
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [removing, setRemoving] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const ctl = new AbortController();
    (async () => {
      try {
        const r = await apiFetch("/api/me/watchlist", { signal: ctl.signal });
        if (!r.ok) {
          setLoadError(`Failed to load watchlist (HTTP ${r.status})`);
          return;
        }
        const data = (await r.json()) as WatchlistEntry[];
        setEntries(data);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setLoadError(e instanceof Error ? e.message : "Network error");
      } finally {
        setLoaded(true);
      }
    })();
    return () => ctl.abort();
  }, []);

  const handleRemove = useCallback(async (id: string) => {
    setRemoving((m) => ({ ...m, [id]: true }));
    try {
      const res = await apiFetch(`/api/me/watchlist/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || "Failed to remove from watchlist");
        return;
      }
      setEntries((prev) => prev.filter((e) => e.researcher_id !== id));
      toast.success("Removed from watchlist");
    } catch {
      toast.error("Network error — please try again");
    } finally {
      setRemoving((m) => {
        const next = { ...m };
        delete next[id];
        return next;
      });
    }
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold text-zinc-900 dark:text-white">
            Watchlist {loaded && (
              <span className="ml-2 text-sm font-medium text-zinc-500">
                ({entries.length}/{WATCHLIST_CAP})
              </span>
            )}
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            Researchers you&apos;re tracking — re-analyze any of them and the
            delta vs. their last snapshot lights up here.
          </p>
        </div>
      </div>

      <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="text-sm text-zinc-600 dark:text-zinc-400">
            Tracked researchers
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!loaded ? (
            <ListSkeleton rows={4} />
          ) : loadError ? (
            <div className="flex flex-col items-center py-8 text-sm text-red-700 dark:text-red-300">
              <AlertTriangle className="mb-3 h-10 w-10" />
              {loadError}
            </div>
          ) : entries.length === 0 ? (
            <EmptyState
              icon={<Eye className="h-5 w-5" />}
              title="Your watchlist is empty"
              description="Star researchers from any profile page to add them to your watchlist. You'll see how their integrity score changes over time when you re-analyze them."
              action={{ label: "Browse researchers", href: "/researcher" }}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-200 text-left text-[11px] uppercase tracking-wide text-zinc-500 dark:border-zinc-800">
                    <th className="pb-2 pr-4 font-medium">Researcher</th>
                    <th className="pb-2 pr-4 text-right font-medium">Integrity</th>
                    <th className="pb-2 pr-4 text-right font-medium">Δ vs. last</th>
                    <th className="pb-2 pr-4 font-medium">Last analyzed</th>
                    <th className="pb-2 font-medium" aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e) => (
                    <WatchlistRow
                      key={e.researcher_id}
                      entry={e}
                      removing={!!removing[e.researcher_id]}
                      onRemove={() => handleRemove(e.researcher_id)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function WatchlistRow({
  entry,
  removing,
  onRemove,
}: {
  entry: WatchlistEntry;
  removing: boolean;
  onRemove: () => void;
}) {
  const score = entry.integrity_score;
  const delta = entry.integrity_score_delta;

  // Delta color/icon: positive → emerald + up, negative → red + down, 0 → muted minus.
  let deltaIcon = <Minus className="h-3 w-3" />;
  let deltaClass = "text-zinc-500";
  if (delta != null) {
    if (delta > 0) {
      deltaIcon = <ArrowUp className="h-3 w-3" />;
      deltaClass = "text-emerald-700 dark:text-emerald-400";
    } else if (delta < 0) {
      deltaIcon = <ArrowDown className="h-3 w-3" />;
      deltaClass = "text-red-700 dark:text-red-400";
    }
  }

  return (
    <tr className="border-b border-zinc-200/70 dark:border-zinc-800/50">
      <td className="py-2.5 pr-4">
        <Link
          href={`/researcher/${entry.researcher_id}`}
          className="block min-w-0"
        >
          <p className="truncate text-sm font-medium text-zinc-900 hover:text-accent-amber dark:text-white">
            {entry.researcher_name}
          </p>
          <p className="truncate text-xs text-zinc-500">
            {entry.institution || "Unknown institution"}
          </p>
        </Link>
      </td>
      <td className="py-2.5 pr-4 text-right">
        {score != null ? (
          <span className={`font-bold tabular-nums ${scoreColor(score)}`}>
            {Math.round(score)}
          </span>
        ) : (
          <Badge className="bg-blue-500/20 text-[10px] text-blue-700 dark:text-blue-400">
            pending
          </Badge>
        )}
      </td>
      <td className="py-2.5 pr-4 text-right">
        {delta == null ? (
          <span className="text-xs text-zinc-500">—</span>
        ) : (
          <span
            className={`inline-flex items-center gap-1 font-medium tabular-nums ${deltaClass}`}
          >
            {deltaIcon}
            {delta > 0 ? "+" : ""}
            {delta.toFixed(1)}
          </span>
        )}
      </td>
      <td className="py-2.5 pr-4 text-xs text-zinc-500">
        {entry.last_analyzed_at
          ? new Date(entry.last_analyzed_at).toLocaleDateString()
          : "—"}
      </td>
      <td className="py-2.5 text-right">
        <Button
          variant="ghost"
          size="sm"
          onClick={onRemove}
          disabled={removing}
          aria-label={`Remove ${entry.researcher_name} from watchlist`}
          className="h-8 px-2 text-zinc-500 hover:text-red-700 dark:hover:text-red-400"
        >
          {removing ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Trash2 className="h-4 w-4" />
          )}
        </Button>
      </td>
    </tr>
  );
}
