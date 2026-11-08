import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { act, render, renderHook } from "@testing-library/react";

import { TourProvider, useTour } from "./TourContext";
import { TOURS, DASHBOARD_WELCOME_TOUR } from "@/lib/tours";

const STORAGE_KEY = "artiproof.tours";

function wrapper({ children }: { children: React.ReactNode }) {
  return <TourProvider>{children}</TourProvider>;
}

describe("TourContext", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it("starts a tour when called and exposes step state", () => {
    const { result } = renderHook(() => useTour(), { wrapper });

    expect(result.current.activeTour).toBeNull();

    act(() => {
      result.current.startTour(DASHBOARD_WELCOME_TOUR.id);
    });

    expect(result.current.activeTour?.id).toBe(DASHBOARD_WELCOME_TOUR.id);
    expect(result.current.stepIndex).toBe(0);
    expect(result.current.isFirstStep).toBe(true);
    expect(result.current.totalSteps).toBe(
      DASHBOARD_WELCOME_TOUR.steps.length,
    );
  });

  it("advances and rewinds through steps", () => {
    const { result } = renderHook(() => useTour(), { wrapper });

    act(() => {
      result.current.startTour(DASHBOARD_WELCOME_TOUR.id);
    });
    act(() => result.current.nextStep());
    expect(result.current.stepIndex).toBe(1);
    act(() => result.current.prevStep());
    expect(result.current.stepIndex).toBe(0);
    // prevStep is clamped — going below zero stays at zero.
    act(() => result.current.prevStep());
    expect(result.current.stepIndex).toBe(0);
  });

  it("calling nextStep on the final step ends the tour and persists completion", async () => {
    const { result } = renderHook(() => useTour(), { wrapper });

    act(() => {
      result.current.startTour(DASHBOARD_WELCOME_TOUR.id);
    });
    // Jump to the last step by clicking next n-1 times.
    const totalSteps = DASHBOARD_WELCOME_TOUR.steps.length;
    for (let i = 0; i < totalSteps - 1; i++) {
      act(() => result.current.nextStep());
    }
    expect(result.current.isLastStep).toBe(true);

    await act(async () => {
      result.current.nextStep();
      // endTour is queued in a microtask after nextStep on last step.
      await Promise.resolve();
    });

    expect(result.current.activeTour).toBeNull();
    expect(result.current.isCompleted(DASHBOARD_WELCOME_TOUR.id)).toBe(true);

    const raw = window.localStorage.getItem(STORAGE_KEY);
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed.completed[DASHBOARD_WELCOME_TOUR.id]).toBe(
      DASHBOARD_WELCOME_TOUR.version,
    );
  });

  it("skipTour also marks completion (Skip ≡ Done — don't pester)", () => {
    const { result } = renderHook(() => useTour(), { wrapper });

    act(() => {
      result.current.startTour(DASHBOARD_WELCOME_TOUR.id);
    });
    act(() => result.current.skipTour());

    expect(result.current.activeTour).toBeNull();
    expect(result.current.isCompleted(DASHBOARD_WELCOME_TOUR.id)).toBe(true);
  });

  it("startTour is a no-op when the tour is already completed at the same version", () => {
    // Pre-populate completed storage.
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        v: 1,
        completed: {
          [DASHBOARD_WELCOME_TOUR.id]: DASHBOARD_WELCOME_TOUR.version,
        },
      }),
    );

    const { result } = renderHook(() => useTour(), { wrapper });

    act(() => {
      result.current.startTour(DASHBOARD_WELCOME_TOUR.id);
    });
    expect(result.current.activeTour).toBeNull();
  });

  it("startTour with {force: true} runs even when already completed", () => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        v: 1,
        completed: {
          [DASHBOARD_WELCOME_TOUR.id]: DASHBOARD_WELCOME_TOUR.version,
        },
      }),
    );

    const { result } = renderHook(() => useTour(), { wrapper });

    act(() => {
      result.current.startTour(DASHBOARD_WELCOME_TOUR.id, { force: true });
    });
    expect(result.current.activeTour?.id).toBe(DASHBOARD_WELCOME_TOUR.id);
  });

  it("resetTour clears completion so the next start re-runs the flow", () => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        v: 1,
        completed: {
          [DASHBOARD_WELCOME_TOUR.id]: DASHBOARD_WELCOME_TOUR.version,
        },
      }),
    );

    const { result } = renderHook(() => useTour(), { wrapper });

    expect(result.current.isCompleted(DASHBOARD_WELCOME_TOUR.id)).toBe(true);

    act(() => {
      result.current.resetTour(DASHBOARD_WELCOME_TOUR.id);
    });
    expect(result.current.isCompleted(DASHBOARD_WELCOME_TOUR.id)).toBe(false);

    act(() => {
      result.current.startTour(DASHBOARD_WELCOME_TOUR.id);
    });
    expect(result.current.activeTour?.id).toBe(DASHBOARD_WELCOME_TOUR.id);
  });

  it("ignores unknown tour ids gracefully", () => {
    const { result } = renderHook(() => useTour(), { wrapper });
    act(() => result.current.startTour("does-not-exist"));
    expect(result.current.activeTour).toBeNull();
  });

  it("renders without crashing inside <TourProvider>", () => {
    const { container } = render(
      <TourProvider>
        <div data-testid="probe">ok</div>
      </TourProvider>,
    );
    expect(container.querySelector('[data-testid="probe"]')).not.toBeNull();
  });

  it("known tours are registered in TOURS by id", () => {
    expect(TOURS[DASHBOARD_WELCOME_TOUR.id]).toBe(DASHBOARD_WELCOME_TOUR);
  });
});
