"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiFetch } from "@/lib/api";
import { scoreColor } from "@/lib/colors";
import { FileText, Loader2, Search, Users } from "lucide-react";

/**
 * Global Cmd/Ctrl+K command palette. Searches the user's source checks,
 * researcher analyses, and reports via /api/dashboard/search and dispatches
 * to the appropriate detail page on select. Mounted once per dashboard.
 */

type Kind = "source_check" | "researcher" | "report";

interface SearchItem {
  kind: Kind;
  id: string;
  title: string;
  subtitle?: string | null;
  score?: number | null;
  created_at: string | null;
}

interface SearchResponse {
  q: string;
  items: SearchItem[];
}

const DEBOUNCE_MS = 200;

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (next: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<SearchItem[]>([]);
  const [loading, setLoading] = useState(false);

  // Reset state every time the dialog closes so reopening starts fresh.
  useEffect(() => {
    if (!open) {
      setQuery("");
      setItems([]);
      setLoading(false);
    }
  }, [open]);

  // Debounced server search with abort. Empty query resets to idle.
  useEffect(() => {
    if (!open) return;
    const trimmed = query.trim();
    if (!trimmed) {
      setItems([]);
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const res = await apiFetch(
          `/api/dashboard/search?q=${encodeURIComponent(trimmed)}&limit=20`,
          { signal: controller.signal },
        );
        if (!res.ok) {
          setItems([]);
          return;
        }
        const body = (await res.json()) as SearchResponse;
        setItems(Array.isArray(body.items) ? body.items : []);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setItems([]);
      } finally {
        setLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => {
      controller.abort();
      clearTimeout(t);
    };
  }, [open, query]);

  const grouped = useMemo(() => {
    const buckets: Record<Kind, SearchItem[]> = {
      source_check: [],
      researcher: [],
      report: [],
    };
    for (const item of items) buckets[item.kind].push(item);
    return buckets;
  }, [items]);

  const onSelect = useCallback(
    (item: SearchItem) => {
      const href =
        item.kind === "source_check"
          ? `/check/${item.id}`
          : item.kind === "researcher"
            ? `/researcher/${item.id}`
            : "/reports";
      onOpenChange(false);
      router.push(href);
    },
    [onOpenChange, router],
  );

  const trimmed = query.trim();
  const showIdle = !trimmed;
  const showLoading = !!trimmed && loading && items.length === 0;
  const showEmpty = !!trimmed && !loading && items.length === 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="top-[20%] -translate-y-0 gap-0 overflow-hidden p-0 sm:max-w-xl"
      >
        <DialogHeader className="sr-only">
          <DialogTitle>Search</DialogTitle>
          <DialogDescription>
            Search source checks, researchers, and reports.
          </DialogDescription>
        </DialogHeader>
        {/* shouldFilter={false} — server already filters; cmdk's local filter
             would re-drop items whose title doesn't match (we also match on
             input_content / institution / orcid server-side). */}
        <Command shouldFilter={false} className="bg-transparent">
          <div className="flex items-center gap-2 border-b border-zinc-200 px-3 dark:border-zinc-800">
            <Search
              aria-hidden="true"
              className="h-4 w-4 shrink-0 text-zinc-400"
            />
            <Command.Input
              autoFocus
              value={query}
              onValueChange={setQuery}
              placeholder="Search source checks, researchers, reports…"
              className="flex h-12 w-full bg-transparent text-sm text-zinc-900 outline-none placeholder:text-zinc-400 dark:text-zinc-100 dark:placeholder:text-zinc-500"
            />
            {loading && trimmed && (
              <Loader2
                aria-hidden="true"
                className="h-4 w-4 shrink-0 animate-spin text-zinc-400"
              />
            )}
          </div>
          <Command.List className="max-h-[340px] overflow-y-auto px-1 py-2">
            {showIdle && (
              <div className="px-3 py-8 text-center text-sm text-zinc-500 dark:text-zinc-400">
                Type to search across your work
              </div>
            )}
            {showLoading && (
              <div className="flex items-center justify-center px-3 py-8 text-sm text-zinc-500 dark:text-zinc-400">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Searching…
              </div>
            )}
            {showEmpty && (
              <div className="px-3 py-8 text-center text-sm text-zinc-500 dark:text-zinc-400">
                No matches for &ldquo;{trimmed}&rdquo;
              </div>
            )}
            {!showIdle && !showEmpty && (
              <>
                <ResultGroup
                  heading="Source checks"
                  Icon={Search}
                  items={grouped.source_check}
                  onSelect={onSelect}
                />
                <ResultGroup
                  heading="Researchers"
                  Icon={Users}
                  items={grouped.researcher}
                  onSelect={onSelect}
                />
                <ResultGroup
                  heading="Reports"
                  Icon={FileText}
                  items={grouped.report}
                  onSelect={onSelect}
                />
              </>
            )}
          </Command.List>
          <div className="flex items-center justify-end gap-3 border-t border-zinc-200 bg-zinc-50/60 px-3 py-2 text-[11px] text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
            <span>
              <Kbd>Esc</Kbd> to close
            </span>
            <span>
              <Kbd>↑</Kbd>
              <Kbd>↓</Kbd> to navigate
            </span>
            <span>
              <Kbd>↵</Kbd> to select
            </span>
          </div>
        </Command>
      </DialogContent>
    </Dialog>
  );
}

function ResultGroup({
  heading,
  Icon,
  items,
  onSelect,
}: {
  heading: string;
  Icon: React.ComponentType<{ className?: string }>;
  items: SearchItem[];
  onSelect: (item: SearchItem) => void;
}) {
  if (items.length === 0) return null;
  return (
    <Command.Group
      heading={heading}
      className="px-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:pb-1.5 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-zinc-500 dark:[&_[cmdk-group-heading]]:text-zinc-400"
    >
      {items.map((item) => (
        <Command.Item
          key={`${item.kind}:${item.id}`}
          value={`${item.kind}:${item.id}:${item.title}`}
          onSelect={() => onSelect(item)}
          className="flex cursor-pointer select-none items-center gap-3 rounded-md px-2 py-2 text-sm text-zinc-700 outline-none aria-selected:bg-brand/10 aria-selected:text-brand data-[selected=true]:bg-brand/10 data-[selected=true]:text-brand dark:text-zinc-300 dark:aria-selected:bg-brand/20 dark:aria-selected:text-brand-fg dark:data-[selected=true]:bg-brand/20 dark:data-[selected=true]:text-brand-fg"
        >
          <Icon
            aria-hidden="true"
            className="h-4 w-4 shrink-0 text-zinc-400 dark:text-zinc-500"
          />
          <div className="min-w-0 flex-1">
            <p className="truncate">{item.title}</p>
            {item.subtitle && (
              <p className="truncate text-[11px] text-zinc-500 dark:text-zinc-400">
                {item.subtitle}
              </p>
            )}
          </div>
          {item.score != null && (
            <span
              className={`shrink-0 rounded-md border border-zinc-200 px-1.5 py-0.5 text-[10px] font-bold tabular-nums dark:border-zinc-800 ${scoreColor(item.score)}`}
            >
              {item.score.toFixed(0)}
            </span>
          )}
        </Command.Item>
      ))}
    </Command.Group>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="ml-0.5 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded border border-zinc-300 bg-white px-1 font-mono text-[10px] text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
      {children}
    </kbd>
  );
}

// Platform detection via useSyncExternalStore — server snapshot returns null
// (no nav object yet), client snapshot returns the resolved bool. React hands
// us the post-hydration value without us doing setState in an effect.
function getIsMacSnapshot(): boolean | null {
  if (typeof navigator === "undefined") return null;
  const ua = navigator.userAgent || "";
  const platform = navigator.platform || "";
  return /Mac|iPhone|iPod|iPad/i.test(platform) || /Mac OS X/.test(ua);
}

// `subscribe` is a no-op — the value never changes after first render.
function subscribePlatform() {
  return () => {};
}

/**
 * Hook that wires the global Cmd/Ctrl+K hotkey to a piece of state.
 * Returns `[open, setOpen]` plus a `platform` flag for the kbd hint.
 *
 * Hotkey: Cmd+K on macOS, Ctrl+K elsewhere. Both modifier combos work
 * regardless of platform so users on multi-OS muscle memory don't fight
 * the listener. The typing-target guard from KeyboardShortcutsPanel doesn't
 * apply — Cmd+K is a chord, not a single content key, so we always toggle.
 */
export function useCommandPalette() {
  const [open, setOpen] = useState(false);
  // Server snapshot returns null so SSR markup is stable; the client picks up
  // the real value on first paint. Render the kbd only once isMac !== null
  // to avoid a Ctrl+K → ⌘K flash on Mac users.
  const isMac = useSyncExternalStore(
    subscribePlatform,
    getIsMacSnapshot,
    () => null,
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        // We intentionally don't gate on isTypingTarget — Cmd+K is a chord,
        // and the user may invoke it from anywhere (including the very
        // header search button if it had focus).
        event.preventDefault();
        setOpen((prev) => !prev);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return { open, setOpen, isMac };
}

export default CommandPalette;
