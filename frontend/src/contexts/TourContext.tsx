"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { TOURS, type TourDefinition, type TourStep } from "@/lib/tours";

/**
 * Onboarding tour state machine.
 *
 * The provider owns:
 *   - which tour (if any) is currently running,
 *   - the current step index inside it,
 *   - the set of completed (tourId, version) pairs persisted to
 *     localStorage so we don't re-show on subsequent visits.
 *
 * The overlay component subscribes and renders the spotlight + tooltip.
 *
 * Storage shape (versioned so we can change it cleanly):
 *
 *   {
 *     v: 1,
 *     completed: {
 *       "dashboard-welcome": 1,        // tour id -> highest completed version
 *       "feature-x-tour":   2,
 *     }
 *   }
 */

const STORAGE_KEY = "artiproof.tours";
const STORAGE_VERSION = 1;

interface StoredTours {
  v: number;
  completed: Record<string, number>;
}

function loadStored(): StoredTours {
  if (typeof window === "undefined") {
    return { v: STORAGE_VERSION, completed: {} };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { v: STORAGE_VERSION, completed: {} };
    const parsed = JSON.parse(raw) as StoredTours;
    if (parsed?.v !== STORAGE_VERSION) {
      return { v: STORAGE_VERSION, completed: {} };
    }
    if (!parsed.completed || typeof parsed.completed !== "object") {
      return { v: STORAGE_VERSION, completed: {} };
    }
    return parsed;
  } catch {
    return { v: STORAGE_VERSION, completed: {} };
  }
}

function persistStored(state: StoredTours) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // localStorage may be disabled / quota exceeded — completion is
    // best-effort. The worst case is the user sees the tour twice.
  }
}

interface TourContextValue {
  activeTour: TourDefinition | null;
  currentStep: TourStep | null;
  stepIndex: number;
  totalSteps: number;
  isFirstStep: boolean;
  isLastStep: boolean;
  startTour: (tourId: string, opts?: { force?: boolean }) => void;
  endTour: () => void;
  skipTour: () => void;
  nextStep: () => void;
  prevStep: () => void;
  isCompleted: (tourId: string) => boolean;
  /** Wipes completion for a tour — used by Settings "Replay tour". */
  resetTour: (tourId: string) => void;
}

const TourContext = createContext<TourContextValue | null>(null);

export function TourProvider({ children }: { children: ReactNode }) {
  const [activeTour, setActiveTour] = useState<TourDefinition | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [completed, setCompleted] = useState<Record<string, number>>({});
  // We hold a ref so end-of-tour analytics doesn't fire twice if React
  // batches a state flush that re-runs the effect.
  const finishingRef = useRef<string | null>(null);

  // Read stored completion once on mount. We can't lazy-init useState
  // from localStorage in a "use client" component because Next.js does a
  // server render first and the values would mismatch — read on mount
  // is the established pattern in this codebase (see ColorModeContext,
  // CookieBanner). The lint rule against setState-in-effect treats this
  // as an exception by convention; the disable comment is required.
  useEffect(() => {
    const stored = loadStored();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCompleted(stored.completed);
  }, []);

  const markCompleted = useCallback((tourId: string, version: number) => {
    setCompleted((prev) => {
      const next = { ...prev, [tourId]: version };
      persistStored({ v: STORAGE_VERSION, completed: next });
      return next;
    });
  }, []);

  const startTour = useCallback(
    (tourId: string, opts?: { force?: boolean }) => {
      const tour = TOURS[tourId];
      if (!tour) {
        if (process.env.NODE_ENV !== "production") {
          console.warn(`[tour] unknown tour id: ${tourId}`);
        }
        return;
      }
      // If already completed at this version and the caller didn't
      // force, ignore. This makes auto-start idempotent.
      const completedVersion = completed[tourId] ?? -1;
      if (!opts?.force && completedVersion >= tour.version) return;
      finishingRef.current = null;
      setStepIndex(0);
      setActiveTour(tour);
    },
    [completed],
  );

  const endTour = useCallback(() => {
    if (!activeTour) return;
    if (finishingRef.current === activeTour.id) return;
    finishingRef.current = activeTour.id;
    markCompleted(activeTour.id, activeTour.version);
    setActiveTour(null);
    setStepIndex(0);
  }, [activeTour, markCompleted]);

  const skipTour = useCallback(() => {
    // Skipping ALSO counts as completion — we don't pester the user.
    // They can replay from Settings if they change their mind.
    endTour();
  }, [endTour]);

  const nextStep = useCallback(() => {
    if (!activeTour) return;
    setStepIndex((idx) => {
      if (idx >= activeTour.steps.length - 1) {
        // Last step. Defer endTour to the next microtask so the
        // tooltip's exit animation has a frame to start before the
        // overlay unmounts.
        queueMicrotask(endTour);
        return idx;
      }
      return idx + 1;
    });
  }, [activeTour, endTour]);

  const prevStep = useCallback(() => {
    setStepIndex((idx) => (idx > 0 ? idx - 1 : 0));
  }, []);

  const isCompleted = useCallback(
    (tourId: string) => {
      const tour = TOURS[tourId];
      if (!tour) return false;
      return (completed[tourId] ?? -1) >= tour.version;
    },
    [completed],
  );

  const resetTour = useCallback((tourId: string) => {
    setCompleted((prev) => {
      if (!(tourId in prev)) return prev;
      const next = { ...prev };
      delete next[tourId];
      persistStored({ v: STORAGE_VERSION, completed: next });
      return next;
    });
  }, []);

  const currentStep: TourStep | null = activeTour
    ? activeTour.steps[stepIndex] ?? null
    : null;

  const value = useMemo<TourContextValue>(
    () => ({
      activeTour,
      currentStep,
      stepIndex,
      totalSteps: activeTour?.steps.length ?? 0,
      isFirstStep: stepIndex === 0,
      isLastStep: activeTour
        ? stepIndex === activeTour.steps.length - 1
        : false,
      startTour,
      endTour,
      skipTour,
      nextStep,
      prevStep,
      isCompleted,
      resetTour,
    }),
    [
      activeTour,
      currentStep,
      stepIndex,
      startTour,
      endTour,
      skipTour,
      nextStep,
      prevStep,
      isCompleted,
      resetTour,
    ],
  );

  return <TourContext.Provider value={value}>{children}</TourContext.Provider>;
}

export function useTour(): TourContextValue {
  const ctx = useContext(TourContext);
  if (!ctx) {
    throw new Error("useTour must be used inside TourProvider");
  }
  return ctx;
}
