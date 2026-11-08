import { describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";

import { useDebouncedValue } from "./use-debounced-value";

describe("useDebouncedValue", () => {
  it("returns the initial value immediately", () => {
    const { result } = renderHook(() => useDebouncedValue("first", 200));
    expect(result.current).toBe("first");
  });

  it("delays updates by the given ms", () => {
    vi.useFakeTimers();
    try {
      const { result, rerender } = renderHook(
        ({ value }) => useDebouncedValue(value, 300),
        { initialProps: { value: "a" } }
      );

      rerender({ value: "b" });
      expect(result.current).toBe("a"); // not yet flushed

      act(() => {
        vi.advanceTimersByTime(150);
      });
      expect(result.current).toBe("a"); // still in the dead zone

      act(() => {
        vi.advanceTimersByTime(200);
      });
      expect(result.current).toBe("b");
    } finally {
      vi.useRealTimers();
    }
  });

  it("coalesces back-to-back updates into one (the latest wins)", () => {
    vi.useFakeTimers();
    try {
      const { result, rerender } = renderHook(
        ({ value }) => useDebouncedValue(value, 300),
        { initialProps: { value: "a" } }
      );

      rerender({ value: "b" });
      act(() => {
        vi.advanceTimersByTime(100);
      });
      rerender({ value: "c" });
      act(() => {
        vi.advanceTimersByTime(100);
      });
      rerender({ value: "d" });
      act(() => {
        // Now wait the full delay since the last update.
        vi.advanceTimersByTime(300);
      });

      expect(result.current).toBe("d");
    } finally {
      vi.useRealTimers();
    }
  });
});
