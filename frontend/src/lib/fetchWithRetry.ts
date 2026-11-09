/**
 * Retry wrapper around fetch for transient failures.
 *
 * Retries on network errors and 5xx responses. 4xx (auth, validation) is
 * returned immediately so callers can show a real error to the user
 * instead of silently retrying a fixable mistake.
 *
 * Honors AbortSignal: if the caller aborts, we surface the AbortError
 * without retrying.
 */
export async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  maxRetries = 2,
  baseDelayMs = 600,
): Promise<Response> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(url, options);
      // 4xx is not retryable — caller's bug or a real error to display
      if (res.ok || res.status < 500) return res;
      lastError = new Error(`HTTP ${res.status}`);
    } catch (e) {
      // Don't retry deliberate aborts
      if (e instanceof DOMException && e.name === "AbortError") throw e;
      lastError = e as Error;
    }

    if (attempt < maxRetries) {
      // Exponential backoff with jitter
      const delay = baseDelayMs * 2 ** attempt * (0.5 + Math.random());
      await new Promise((r) => setTimeout(r, delay));
    }
  }

  throw lastError ?? new Error("fetchWithRetry exhausted");
}
