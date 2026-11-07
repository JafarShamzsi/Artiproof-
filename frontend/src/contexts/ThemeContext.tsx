"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useSyncExternalStore,
  type ReactNode,
} from "react";

const STORAGE_KEY = "artiproof-high-contrast";

type ThemeContextValue = {
  highContrast: boolean;
  toggleHighContrast: () => void;
  setHighContrast: (value: boolean) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

const listeners = new Set<() => void>();

function subscribe(cb: () => void) {
  listeners.add(cb);
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) cb();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", onStorage);
  };
}

function notify() {
  listeners.forEach((cb) => cb());
}

function getSnapshot(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function getServerSnapshot(): boolean {
  return false;
}

function writeHighContrast(value: boolean) {
  try {
    localStorage.setItem(STORAGE_KEY, value ? "true" : "false");
  } catch {
    // localStorage unavailable
  }
  notify();
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const highContrast = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot
  );

  useEffect(() => {
    const root = document.documentElement;
    if (highContrast) {
      root.setAttribute("data-high-contrast", "true");
    } else {
      root.removeAttribute("data-high-contrast");
    }
  }, [highContrast]);

  const setHighContrast = useCallback((value: boolean) => {
    writeHighContrast(value);
  }, []);

  const toggleHighContrast = useCallback(() => {
    writeHighContrast(!getSnapshot());
  }, []);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.altKey && (e.key === "h" || e.key === "H")) {
        e.preventDefault();
        writeHighContrast(!getSnapshot());
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <ThemeContext.Provider
      value={{ highContrast, toggleHighContrast, setHighContrast }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used inside ThemeProvider");
  }
  return ctx;
}
