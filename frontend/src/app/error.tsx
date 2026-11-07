"use client";

import { useEffect } from "react";
import Link from "next/link";

// Next.js 16 passes `unstable_retry` (renamed from `reset`). Calling it
// re-renders the failing segment.
export default function GlobalError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  useEffect(() => {
    console.error("App error boundary caught:", error);
  }, [error]);

  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center bg-zinc-950 px-6 text-center">
      <h1 className="text-4xl font-bold text-white">Something went wrong</h1>
      <p className="mt-4 max-w-md text-sm text-zinc-400">
        {error.message || "An unexpected error occurred."}
      </p>
      {error.digest && (
        <p className="mt-2 text-xs text-zinc-600">Reference: {error.digest}</p>
      )}
      <div className="mt-8 flex gap-3">
        <button
          onClick={() => unstable_retry()}
          className="rounded-lg bg-emerald-500 px-6 py-3 text-sm font-medium text-white transition hover:bg-emerald-600"
        >
          Try again
        </button>
        <Link
          href="/"
          className="rounded-lg border border-zinc-700 px-6 py-3 text-sm font-medium text-zinc-300 transition hover:border-zinc-600 hover:text-white"
        >
          Go home
        </Link>
      </div>
    </div>
  );
}
