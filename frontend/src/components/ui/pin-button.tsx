"use client";

import { useEffect, useState } from "react";
import { Loader2, Star } from "lucide-react";

import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";

type PinKind = "source_check" | "researcher" | "report";

interface PinnedItemResponse {
  kind: PinKind;
  id: string;
}

/**
 * Header-row "pin to dashboard" toggle for detail pages.
 *
 * Fetches the user's pin list once on mount to determine the initial state.
 * Click toggles between POST /api/auth/me/pins and DELETE /api/auth/me/pins/{kind}/{id}.
 *
 * Matches the visual treatment of the sibling "Share" button (outline,
 * size="sm") so the header row reads as a single group of secondary actions.
 */
export function PinButton({
  kind,
  id,
  className = "",
}: {
  kind: PinKind;
  id: string;
  className?: string;
}) {
  const [pinned, setPinned] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const res = await apiFetch("/api/auth/me/pins", {
          signal: controller.signal,
        });
        if (!res.ok) {
          setPinned(false);
          return;
        }
        const items = (await res.json()) as PinnedItemResponse[];
        setPinned(
          Array.isArray(items) &&
            items.some((p) => p.kind === kind && p.id === id),
        );
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setPinned(false);
      }
    })();
    return () => controller.abort();
  }, [kind, id]);

  async function toggle() {
    if (busy || pinned == null) return;
    setBusy(true);
    try {
      if (pinned) {
        const res = await apiFetch(`/api/auth/me/pins/${kind}/${id}`, {
          method: "DELETE",
        });
        if (res.ok || res.status === 204) {
          setPinned(false);
        }
      } else {
        const res = await apiFetch("/api/auth/me/pins", {
          method: "POST",
          body: JSON.stringify({ kind, id }),
        });
        if (res.ok) {
          setPinned(true);
        }
      }
    } finally {
      setBusy(false);
    }
  }

  const isPinned = pinned === true;

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={toggle}
      disabled={busy || pinned == null}
      aria-pressed={isPinned}
      aria-label={isPinned ? "Unpin from dashboard" : "Pin to dashboard"}
      className={
        "border-zinc-300 text-zinc-700 dark:border-zinc-700 dark:text-zinc-400 " +
        className
      }
    >
      {busy ? (
        <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
      ) : (
        <Star
          className="mr-1.5 h-4 w-4"
          fill={isPinned ? "currentColor" : "none"}
          aria-hidden="true"
        />
      )}
      {isPinned ? "Pinned" : "Pin"}
    </Button>
  );
}
