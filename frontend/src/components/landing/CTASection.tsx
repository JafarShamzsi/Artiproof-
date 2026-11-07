import Link from "next/link";
import { ArrowRight } from "lucide-react";

export function CTASection() {
  return (
    <section className="px-6 py-24">
      <div className="mx-auto max-w-4xl">
        <div className="relative overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/30 p-10 text-center sm:p-14">
          {/* Soft radial spotlight backing the CTA. Scoped inside the
              wrapper so it doesn't bleed into the section divider above. */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0"
            style={{
              backgroundImage:
                "radial-gradient(circle at 50% 60%, rgba(16,185,129,0.08), transparent 60%)",
            }}
          />

          <div className="relative">
            <h2 className="font-display text-3xl font-bold tracking-tight text-balance text-white sm:text-4xl">
              Start checking research integrity in 90 seconds.
            </h2>
            <p className="mx-auto mt-4 max-w-lg text-base text-zinc-400 sm:text-lg">
              Free for your first 10 analyses. No credit card, no commitment.
            </p>

            <div className="mt-10 flex flex-col items-center gap-3">
              <Link
                href="/register"
                className="cta-glow group inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-emerald-500 px-7 text-sm font-semibold text-white shadow-lg shadow-emerald-500/20 transition-all hover:bg-emerald-600 active:translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50"
              >
                Start free analysis
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <p className="text-xs text-zinc-500">
                No credit card · 10 checks per month · Cancel anytime
              </p>
            </div>

            <p className="mt-10 text-xs text-zinc-600">
              Built for researchers across ADA University, Baku State
              University, and Khazar University.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
