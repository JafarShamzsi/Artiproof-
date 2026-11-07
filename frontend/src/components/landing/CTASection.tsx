import Link from "next/link";
import { ArrowRight } from "lucide-react";

export function CTASection() {
  return (
    <section className="border-t border-zinc-900 py-32">
      <div className="mx-auto max-w-2xl px-6 text-center">
        <h2 className="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Ten free checks. No credit card.
        </h2>
        <p className="mx-auto mt-4 max-w-lg text-lg text-zinc-400">
          Run your first analysis in under two minutes. Upgrade to Pro when
          your free quota runs out, not before.
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
      </div>
    </section>
  );
}
