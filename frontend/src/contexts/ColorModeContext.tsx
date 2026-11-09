"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

/**
 * Light / dark color mode with system fallback.
 *
 * - Persists to `localStorage["artiproof-theme"]` as "light" | "dark" | "system".
 * - On first paint we read the value via an inline pre-hydration script in
 *   the root layout, so there's no light-flash on a dark-preferring user.
 * - The `dark` class on <html> is the source of truth for Tailwind's `dark:`
 *   variant. CSS variables in :root vs html.dark do the rest.
 *
 * This is independent of `ThemeContext` (high-contrast accessibility).
 */

type ColorMode = "light" | "dark" | "system";
const STORAGE_KEY = "artiproof-theme";

interface ColorModeContextValue {
  mode: ColorMode;
  resolved: "light" | "dark";
  setMode: (mode: ColorMode) => void;
}

const ColorModeContext = createContext<ColorModeContextValue | null>(null);

function readStoredMode(): ColorMode {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    // ignore
  }
  return "system";
}

function systemPrefersDark(): boolean {
  if (typeof window === "undefined") return true; // dark-first SSR
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyMode(mode: ColorMode): "light" | "dark" {
  const resolved =
    mode === "system" ? (systemPrefersDark() ? "dark" : "light") : mode;
  const root = document.documentElement;
  root.classList.toggle("dark", resolved === "dark");
  root.style.colorScheme = resolved;
  return resolved;
}

export function ColorModeProvider({ children }: { children: ReactNode }) {
  // Lazy initializer so the *first* client render already reflects the
  // stored preference. SSR always sees "system"/"dark" (server can't read
  // localStorage); the pre-hydration script in layout.tsx applies the
  // correct class before React mounts, and <html suppressHydrationWarning>
  // tolerates the mismatch. Doing this avoids the
  // react-hooks/set-state-in-effect cascading-render anti-pattern.
  const [mode, setModeState] = useState<ColorMode>(() => {
    if (typeof window === "undefined") return "system";
    return readStoredMode();
  });
  const [resolved, setResolved] = useState<"light" | "dark">(() => {
    if (typeof window === "undefined") return "dark";
    const stored = readStoredMode();
    return stored === "system" ? (systemPrefersDark() ? "dark" : "light") : stored;
  });

  // Re-apply DOM class whenever resolved changes (and on first paint).
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", resolved === "dark");
    root.style.colorScheme = resolved;
  }, [resolved]);

  // When mode is "system", track changes to the OS preference live.
  useEffect(() => {
    if (mode !== "system" || typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => setResolved(systemPrefersDark() ? "dark" : "light");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [mode]);

  const setMode = useCallback((next: ColorMode) => {
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore
    }
    setModeState(next);
    setResolved(applyMode(next));
  }, []);

  return (
    <ColorModeContext.Provider value={{ mode, resolved, setMode }}>
      {children}
    </ColorModeContext.Provider>
  );
}

export function useColorMode(): ColorModeContextValue {
  const ctx = useContext(ColorModeContext);
  if (!ctx) {
    throw new Error("useColorMode must be used inside ColorModeProvider");
  }
  return ctx;
}
