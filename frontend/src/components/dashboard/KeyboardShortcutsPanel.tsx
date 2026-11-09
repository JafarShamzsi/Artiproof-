"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Keyboard } from "lucide-react";

interface ShortcutRow {
  keys: ReadonlyArray<string>;
  label: string;
}

const NAVIGATION_SHORTCUTS: Record<string, string> = {
  d: "/dashboard",
  c: "/check",
  r: "/researcher",
  p: "/reports",
  s: "/settings",
};

const SHORTCUTS: ReadonlyArray<{ heading: string; rows: ReadonlyArray<ShortcutRow> }> = [
  {
    heading: "General",
    rows: [
      { keys: ["?"], label: "Open this panel" },
      { keys: ["Alt", "H"], label: "Toggle high-contrast mode" },
      { keys: ["Esc"], label: "Close any open dialog" },
    ],
  },
  {
    heading: "Navigation",
    rows: [
      { keys: ["g", "d"], label: "Go to Dashboard" },
      { keys: ["g", "c"], label: "Go to Check Source" },
      { keys: ["g", "r"], label: "Go to Analyze Researcher" },
      { keys: ["g", "p"], label: "Go to Reports" },
      { keys: ["g", "s"], label: "Go to Settings" },
    ],
  },
];

/**
 * Returns true when the keyboard event originated from a typing surface
 * (input, textarea, contenteditable). Used to ignore single-letter shortcuts
 * while the user is composing text.
 */
function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (target.isContentEditable) return true;
  return false;
}

export function KeyboardShortcutsPanel() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  // Refs avoid a re-render race in the keydown handler — the chord state
  // changes faster than React batching can flush.
  const pendingGRef = useRef(false);
  const pendingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearPendingG = useCallback(() => {
    pendingGRef.current = false;
    if (pendingTimeoutRef.current) {
      clearTimeout(pendingTimeoutRef.current);
      pendingTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      // Bail when the user is typing or holding a modifier we don't bind.
      if (isTypingTarget(event.target)) {
        clearPendingG();
        return;
      }
      if (event.metaKey || event.ctrlKey || event.altKey) {
        clearPendingG();
        return;
      }

      // Open this panel — `?` lives on Shift+/ on most layouts so we accept
      // either the literal key or `/` with shift held.
      if (event.key === "?" || (event.key === "/" && event.shiftKey)) {
        event.preventDefault();
        clearPendingG();
        setOpen(true);
        return;
      }

      // Continuing a `g + <letter>` chord.
      if (pendingGRef.current) {
        const target = NAVIGATION_SHORTCUTS[event.key.toLowerCase()];
        clearPendingG();
        if (target) {
          event.preventDefault();
          router.push(target);
        }
        return;
      }

      // Starting a `g` chord.
      if (event.key === "g") {
        pendingGRef.current = true;
        pendingTimeoutRef.current = setTimeout(() => {
          pendingGRef.current = false;
          pendingTimeoutRef.current = null;
        }, 1000);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      clearPendingG();
    };
  }, [router, clearPendingG]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Keyboard className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />
            Keyboard shortcuts
          </DialogTitle>
          <DialogDescription>
            Move around ArtiProof faster. Most chords ignore typing in inputs.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-5">
          {SHORTCUTS.map((group) => (
            <div key={group.heading} className="space-y-2">
              <h3 className="text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                {group.heading}
              </h3>
              <ul className="divide-y divide-zinc-200 overflow-hidden rounded-lg border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
                {group.rows.map((row) => (
                  <li
                    key={row.label}
                    className="flex items-center justify-between gap-3 px-3 py-2"
                  >
                    <span className="text-sm text-zinc-700 dark:text-zinc-300">
                      {row.label}
                    </span>
                    <span className="flex items-center gap-1">
                      {row.keys.map((key, idx) => (
                        <span key={`${key}-${idx}`} className="flex items-center gap-1">
                          <kbd className="rounded border border-zinc-300 bg-zinc-100 px-1.5 py-0.5 font-mono text-[11px] text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                            {key}
                          </kbd>
                          {idx < row.keys.length - 1 && (
                            <span className="text-xs text-zinc-400">then</span>
                          )}
                        </span>
                      ))}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default KeyboardShortcutsPanel;
