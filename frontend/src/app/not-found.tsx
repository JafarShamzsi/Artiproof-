import Link from "next/link";

export const metadata = {
  title: "Page not found — ArtiProof",
};

export default function NotFound() {
  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center bg-zinc-50 px-6 text-center dark:bg-zinc-950">
      <p className="text-sm font-medium uppercase tracking-widest text-brand dark:text-brand-fg">
        404
      </p>
      <h1 className="mt-3 text-5xl font-bold text-zinc-900 dark:text-white">Page not found</h1>
      <p className="mt-4 max-w-md text-sm text-zinc-600 dark:text-zinc-400">
        The page you&apos;re looking for doesn&apos;t exist or has moved.
      </p>
      <div className="mt-8 flex gap-3">
        <Link
          href="/"
          className="rounded-lg bg-brand px-6 py-3 text-sm font-medium text-white transition hover:bg-brand-hover"
        >
          Go home
        </Link>
        <Link
          href="/dashboard"
          className="rounded-lg border border-zinc-300 px-6 py-3 text-sm font-medium text-zinc-700 transition hover:border-zinc-400 hover:text-zinc-900 dark:border-zinc-700 dark:text-zinc-300 dark:hover:border-zinc-600 dark:hover:text-white"
        >
          Open dashboard
        </Link>
      </div>
    </div>
  );
}
