import { LampEffect } from "./shared/LampEffect";

export function CTASection() {
  return (
    <LampEffect>
      <div className="mx-auto max-w-2xl px-6 text-center">
        <h2 className="font-display text-4xl font-bold tracking-tight text-white">
          Start Protecting Research Integrity
        </h2>
        <p className="mt-4 text-zinc-400">
          Start with 10 free checks per month. Upgrade to Pro for full access
          to all 5 integrity engines.
        </p>

        <div className="mx-auto mt-8 max-w-md">
          <a
            href="/register"
            className="inline-flex w-full items-center justify-center rounded-lg bg-emerald-500 px-6 py-4 text-lg font-semibold text-white transition-all hover:bg-emerald-600 hover:shadow-lg hover:shadow-emerald-500/20"
          >
            Get Started Free
          </a>
        </div>

        <p className="mt-6 text-sm text-zinc-500">
          Built by the ArtiProof team for the EaP region
        </p>
      </div>
    </LampEffect>
  );
}
