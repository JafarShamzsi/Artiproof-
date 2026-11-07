import Link from "next/link";

export const metadata = {
  title: "Page not found — ArtiProof",
};

export default function NotFound() {
  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center bg-zinc-950 px-6 text-center">
      <p className="text-sm font-medium uppercase tracking-widest text-emerald-400">
        404
      </p>
      <h1 className="mt-3 text-5xl font-bold text-white">Page not found</h1>
      <p className="mt-4 max-w-md text-sm text-zinc-400">
        The page you&apos;re looking for doesn&apos;t exist or has moved.
      </p>
      <div className="mt-8 flex gap-3">
        <Link
          href="/"
          className="rounded-lg bg-emerald-500 px-6 py-3 text-sm font-medium text-white transition hover:bg-emerald-600"
        >
          Go home
        </Link>
        <Link
          href="/dashboard"
          className="rounded-lg border border-zinc-700 px-6 py-3 text-sm font-medium text-zinc-300 transition hover:border-zinc-600 hover:text-white"
        >
          Open dashboard
        </Link>
      </div>
    </div>
  );
}
