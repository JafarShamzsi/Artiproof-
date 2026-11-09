"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

export function analysisIsActive(status?: string): boolean {
  return status === "pending" || status === "processing";
}

/** Keep a running result current even after SSE disconnects or a page reload. */
export function useAnalysisRefresh<T>(
  url: string,
  active: boolean,
  onUpdate: (data: T, signal: AbortSignal) => void | Promise<void>,
): string | null {
  const [error, setError] = useState<{ url: string; message: string } | null>(null);

  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;

    async function refresh() {
      let retry = true;
      try {
        const response = await apiFetch(url, { signal: controller.signal });
        if (!response.ok) {
          retry = ![401, 403, 404].includes(response.status);
          throw new Error(retry
            ? "Updates are temporarily unavailable. Retrying automatically."
            : "Updates are unavailable. Refresh the page to check your access.");
        }
        const data = await response.json() as T;
        if (controller.signal.aborted) return;
        await onUpdate(data, controller.signal);
        if (!controller.signal.aborted) setError(null);
      } catch (cause) {
        if (!controller.signal.aborted) {
          setError({ url, message: cause instanceof Error && cause.message.startsWith("Updates")
            ? cause.message : "Updates are temporarily unavailable. Retrying automatically." });
        }
      } finally {
        // Schedule after completion so slow requests never overlap.
        if (retry && !controller.signal.aborted) timer = setTimeout(refresh, 3000);
      }
    }

    timer = setTimeout(refresh, 3000);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [url, active, onUpdate]);

  return active && error?.url === url ? error.message : null;
}
