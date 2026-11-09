"use client";

import { useEffect, useState } from "react";
import { Eye, EyeOff, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { toast } from "@/lib/toast";

/**
 * Compact watchlist toggle suitable for in-row use on the researcher list,
 * the dashboard's watchlist tile, and anywhere else a user might want a
 * one-click "Watch / Unwatch" affordance without navigating.
 *
 * Initial state is fetched once on mount from `/api/me/watchlist`. If the
 * caller already knows the state (e.g. they have the list in memory),
 * pass `initialWatching` to skip the fetch.
 *
 * Two visual modes:
 *   - `mode="icon"` (default): icon-only, 32x32, no label — for crowded
 *     rows where a full button would push the row's primary affordance
 *     off-screen.
 *   - `mode="full"`: outline Button with label, matching the detail-page
 *     header pattern.
 */
export function WatchlistButton({
  researcherId,
  initialWatching,
  mode = "icon",
  onChange,
  className = "",
}: {
  researcherId: string;
  initialWatching?: boolean;
  mode?: "icon" | "full";
  onChange?: (nextWatching: boolean) => void;
  className?: string;
}) {
  const [watching, setWatching] = useState<boolean | null>(
    initialWatching ?? null,
  );
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (initialWatching !== undefined) return;
    const controller = new AbortController();
    (async () => {
      try {
        const res = await apiFetch("/api/me/watchlist", {
          signal: controller.signal,
        });
        if (!res.ok) {
          setWatching(false);
          return;
        }
        const items = (await res.json()) as Array<{ researcher_id: string }>;
        setWatching(
          Array.isArray(items) &&
            items.some((e) => e.researcher_id === researcherId),
        );
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setWatching(false);
      }
    })();
    return () => controller.abort();
  }, [researcherId, initialWatching]);

  async function toggle(e?: React.MouseEvent | React.KeyboardEvent) {
    // Defend against propagation into a parent <a>/Link wrapper so that
    // clicking the button doesn't ALSO navigate to the researcher page.
    e?.stopPropagation();
    e?.preventDefault();
    if (busy || watching == null) return;
    setBusy(true);
    try {
      if (watching) {
        const res = await apiFetch(`/api/me/watchlist/${researcherId}`, {
          method: "DELETE",
        });
        if (res.ok) {
          setWatching(false);
          onChange?.(false);
          toast.success("Removed from watchlist");
        } else {
          const err = await res.json().catch(() => ({}));
          toast.error(err.detail || "Failed to remove from watchlist");
        }
      } else {
        const res = await apiFetch(`/api/me/watchlist/${researcherId}`, {
          method: "POST",
        });
        if (res.ok) {
          setWatching(true);
          onChange?.(true);
          toast.success("Added to watchlist");
        } else {
          const err = await res.json().catch(() => ({}));
          toast.error(err.detail || "Failed to add to watchlist");
        }
      }
    } finally {
      setBusy(false);
    }
  }

  const isWatching = watching === true;
  const label = isWatching ? "Remove from watchlist" : "Add to watchlist";

  if (mode === "icon") {
    return (
      <button
        type="button"
        onClick={toggle}
        disabled={busy || watching == null}
        aria-pressed={isWatching}
        aria-label={label}
        title={label}
        className={
          "inline-flex h-8 w-8 items-center justify-center rounded-md border border-border-default text-fg-secondary transition-colors hover:bg-brand-soft hover:text-fg-primary disabled:cursor-not-allowed disabled:opacity-60 " +
          className
        }
      >
        {busy ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        ) : isWatching ? (
          <EyeOff className="h-4 w-4" aria-hidden="true" />
        ) : (
          <Eye className="h-4 w-4" aria-hidden="true" />
        )}
      </button>
    );
  }

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={toggle}
      disabled={busy || watching == null}
      aria-pressed={isWatching}
      aria-label={label}
      className={
        "border-border-default text-fg-primary " + className
      }
    >
      {busy ? (
        <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
      ) : isWatching ? (
        <EyeOff className="mr-1.5 h-4 w-4" />
      ) : (
        <Eye className="mr-1.5 h-4 w-4" />
      )}
      {isWatching ? "Watching" : "Watch"}
    </Button>
  );
}
