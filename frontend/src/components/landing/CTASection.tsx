import Link from "next/link";
import { ArrowRight } from "lucide-react";

export function CTASection() {
  return (
    <section className="px-6 py-24 sm:py-28">
      <div className="mx-auto max-w-4xl">
        <div className="relative overflow-hidden rounded-2xl border border-border-default bg-surface-card p-10 text-center sm:p-14">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "radial-gradient(circle at 50% 60%, color-mix(in oklab, var(--brand) 14%, transparent), transparent 65%)",
            }}
          />

          <div className="relative">
            <h2 className="font-display text-4xl font-semibold leading-[1.05] tracking-tight text-balance text-fg-primary sm:text-5xl">
              Start checking research integrity in{" "}
              <span className="italic text-brand-fg">90 seconds.</span>
            </h2>
            <p className="mx-auto mt-5 max-w-lg text-base text-fg-secondary sm:text-lg">
              Free for your first ten analyses. No credit card, no commitment.
            </p>

            <div className="mt-10 flex flex-col items-center gap-3">
              <Link
                href="/register"
                className="cta-glow group inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-brand px-7 text-sm font-semibold text-white shadow-lg shadow-[color:var(--brand)]/25 transition-all hover:bg-brand-hover active:translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
              >
                Start free analysis
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" strokeWidth={2} />
              </Link>
              <p className="text-xs text-fg-tertiary">
                No credit card · 10 checks per month · Cancel anytime
              </p>
            </div>

            <p className="mt-10 text-xs text-fg-tertiary">
              Built for researchers across ADA University, Baku State
              University, and Khazar University.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
