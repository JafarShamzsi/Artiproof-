"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

/**
 * Cookie consent banner.
 *
 * Defaults to **essential cookies only**. Analytics and marketing are
 * opt-in. The user's choice is stored in localStorage with a 12-month
 * expiry; once that passes we re-prompt.
 *
 * Global Privacy Control (GPC) is honoured: if the browser exposes
 * ``navigator.globalPrivacyControl === true`` we record a "rejected"
 * choice automatically and never show the banner. That mirrors the
 * Sec-GPC server header — same intent, client-side enforcement.
 *
 * Persistence shape (versioned so a future change can invalidate old
 * choices cleanly):
 *
 *   {
 *     v: 1,
 *     decidedAt: 1717024838,        // unix seconds
 *     consent: {
 *       essential: true,             // always true; pinned in UI
 *       analytics: false,
 *       marketing: false,
 *     }
 *   }
 *
 * Other components can read the consent state with
 * ``getStoredConsent()`` to gate their own load logic (e.g. only
 * mount an analytics SDK when ``analytics === true``).
 */

const STORAGE_KEY = "artiproof.cookie-consent";
const STORAGE_VERSION = 1;
const TTL_SECONDS = 60 * 60 * 24 * 365; // 12 months

export interface ConsentState {
  essential: true;
  analytics: boolean;
  marketing: boolean;
}

interface StoredConsent {
  v: number;
  decidedAt: number;
  consent: ConsentState;
}

const DEFAULT_DENY: ConsentState = {
  essential: true,
  analytics: false,
  marketing: false,
};

const ACCEPT_ALL: ConsentState = {
  essential: true,
  analytics: true,
  marketing: true,
};

function loadStored(): StoredConsent | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredConsent;
    if (parsed?.v !== STORAGE_VERSION) return null;
    if (typeof parsed.decidedAt !== "number") return null;
    const ageSeconds = Math.floor(Date.now() / 1000) - parsed.decidedAt;
    if (ageSeconds > TTL_SECONDS) return null;
    return parsed;
  } catch {
    return null;
  }
}

function persist(consent: ConsentState): void {
  if (typeof window === "undefined") return;
  const payload: StoredConsent = {
    v: STORAGE_VERSION,
    decidedAt: Math.floor(Date.now() / 1000),
    consent,
  };
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // Storage may be disabled / quota exceeded — fail closed (default
    // deny will be re-applied on next page load).
  }
}

/**
 * Read the current consent without mounting the banner. Useful for
 * other components that need to know whether to load an SDK.
 */
export function getStoredConsent(): ConsentState {
  const stored = loadStored();
  return stored?.consent ?? DEFAULT_DENY;
}

function hasGlobalPrivacyControl(): boolean {
  if (typeof navigator === "undefined") return false;
  // Browsers expose this on the navigator. Type is `unknown` so we
  // probe defensively.
  const nav = navigator as Navigator & { globalPrivacyControl?: boolean };
  return nav.globalPrivacyControl === true;
}

export function CookieBanner() {
  const [visible, setVisible] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [draft, setDraft] = useState<ConsentState>(DEFAULT_DENY);
  // Refs are used to move keyboard focus into the banner when it opens
  // (and into the Customise panel when it expands). Without this, the
  // dialog never receives focus and a keyboard-only user can't act on it.
  const primaryActionRef = useRef<HTMLButtonElement>(null);
  const settingsHeadingRef = useRef<HTMLHeadingElement>(null);
  const bannerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // localStorage and navigator are browser-only — initialising the
    // visibility state from them at useState() time would cause a
    // hydration mismatch (SSR renders one tree, client renders another
    // once the storage read resolves). The post-mount setState is the
    // standard pattern for this; the lint rule is overly conservative
    // for legitimate read-once-on-mount cases.
    //
    // GPC = automatic deny + no banner. Honour the browser signal.
    if (hasGlobalPrivacyControl()) {
      persist(DEFAULT_DENY);
      return;
    }
    if (loadStored() == null) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setVisible(true);
    }
  }, []);

  // Move focus into the banner on first appearance so a keyboard user
  // can immediately act on it. Without this the primary action sits
  // off-tab-order until they reach it.
  useEffect(() => {
    if (visible && !showSettings) {
      // requestAnimationFrame so the focus call lands after the element
      // is mounted but before paint — prevents the focus-flicker some
      // browsers show when focusing mid-render.
      requestAnimationFrame(() => primaryActionRef.current?.focus());
    }
  }, [visible, showSettings]);

  // When the Customise sub-panel opens, move focus to its heading so
  // the next Tab lands on the Essential checkbox rather than back at
  // the dismiss row.
  useEffect(() => {
    if (visible && showSettings) {
      requestAnimationFrame(() => settingsHeadingRef.current?.focus());
    }
  }, [visible, showSettings]);

  // Publish the banner's height as a CSS variable on <html> so the
  // dashboard layout's <main> can reserve exactly enough bottom padding
  // to stop content from being clipped — but ONLY while the banner is
  // visible. When the user dismisses, the variable falls to 0 and pages
  // no longer show 96px of dead padding at the bottom.
  useEffect(() => {
    const root = document.documentElement;
    if (!visible) {
      root.style.removeProperty("--banner-h");
      return;
    }
    const measure = () => {
      const h = bannerRef.current?.offsetHeight ?? 0;
      if (h > 0) root.style.setProperty("--banner-h", `${h}px`);
    };
    measure();
    // The banner expands when the user clicks "Customise" — track its
    // height changes so the layout padding stays in sync. ResizeObserver
    // is absent in jsdom (test env) — fall back to the one-shot measure
    // above and a window resize listener, which is enough for layout
    // sync in dev / prod browsers that lack RO support (none currently).
    const hasResizeObserver = typeof ResizeObserver !== "undefined";
    const ro = hasResizeObserver ? new ResizeObserver(measure) : null;
    if (ro && bannerRef.current) ro.observe(bannerRef.current);
    window.addEventListener("resize", measure);
    return () => {
      ro?.disconnect();
      window.removeEventListener("resize", measure);
      root.style.removeProperty("--banner-h");
    };
  }, [visible]);

  const accept = useCallback((next: ConsentState) => {
    persist(next);
    setVisible(false);
    setShowSettings(false);
  }, []);

  if (!visible) return null;

  return (
    <div
      ref={bannerRef}
      role="dialog"
      aria-modal="false"
      aria-labelledby="cookie-banner-title"
      className="fixed inset-x-0 bottom-0 z-50 border-t border-zinc-700 bg-zinc-900/95 px-4 py-4 backdrop-blur supports-[backdrop-filter]:bg-zinc-900/80"
    >
      <div className="mx-auto flex max-w-5xl flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="flex-1">
          <h2
            id="cookie-banner-title"
            className="text-sm font-semibold text-white"
          >
            Cookies
          </h2>
          <p className="mt-1 text-xs text-zinc-400">
            We use a small set of essential cookies to keep you signed in.
            Analytics and marketing cookies are off by default. See our{" "}
            <Link
              href="/privacy"
              className="text-emerald-400 underline-offset-2 hover:underline"
            >
              privacy policy
            </Link>{" "}
            for details.
          </p>

          {showSettings && (
            <div className="mt-4 space-y-3 rounded-md border border-zinc-700 bg-zinc-950 p-3">
              {/* Focus anchor for keyboard users entering the panel. */}
              <h3
                ref={settingsHeadingRef}
                tabIndex={-1}
                className="text-xs font-semibold uppercase tracking-wide text-zinc-400 focus:outline-none"
              >
                Cookie preferences
              </h3>
              <ConsentRow
                label="Essential"
                description="Required for sign-in and the dashboard to function."
                checked={true}
                disabled
                onChange={() => {}}
              />
              <ConsentRow
                label="Analytics"
                description="Aggregate, anonymised usage to improve the product."
                checked={draft.analytics}
                onChange={(v) => setDraft({ ...draft, analytics: v })}
              />
              <ConsentRow
                label="Marketing"
                description="Cookies for measuring marketing campaign performance."
                checked={draft.marketing}
                onChange={(v) => setDraft({ ...draft, marketing: v })}
              />
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => accept(draft)}
                  className="rounded-md bg-emerald-500 px-3 py-1.5 text-xs font-medium text-zinc-950 hover:bg-emerald-400"
                >
                  Save preferences
                </button>
              </div>
            </div>
          )}
        </div>

        {!showSettings && (
          <div className="flex flex-shrink-0 flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setDraft(DEFAULT_DENY);
                setShowSettings(true);
              }}
              className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-800"
            >
              Customise
            </button>
            <button
              type="button"
              onClick={() => accept(DEFAULT_DENY)}
              className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-800"
            >
              Reject non-essential
            </button>
            <button
              ref={primaryActionRef}
              type="button"
              onClick={() => accept(ACCEPT_ALL)}
              className="rounded-md bg-emerald-500 px-3 py-1.5 text-xs font-medium text-zinc-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300 hover:bg-emerald-400"
            >
              Accept all
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ConsentRow({
  label,
  description,
  checked,
  disabled = false,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 text-xs text-zinc-300">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 cursor-pointer accent-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
      />
      <span>
        <span className="font-medium text-white">{label}</span>
        <span className="ml-1 text-zinc-500">— {description}</span>
      </span>
    </label>
  );
}
