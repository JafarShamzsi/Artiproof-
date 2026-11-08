"use client";

import { useEffect, useState } from "react";

/**
 * Returns a copy of `value` that only updates after `delay` ms of stillness.
 *
 * Use this when an effect/query keys off a fast-changing input (search
 * boxes, range sliders, drag handles) and the downstream work — a
 * fetch, a heavy memo, a router replace — should only fire once typing
 * settles.
 *
 * The original pattern (a useEffect + setTimeout inside the consumer)
 * works but spreads the same five lines across the codebase and makes
 * the delay easy to forget. Centralising here gives one place to tune.
 */
export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);

  return debounced;
}
