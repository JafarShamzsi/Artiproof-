"use client";

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";
import {
  ArrowRight,
  Brain,
  CheckCircle,
  Sparkle,
  XCircle,
} from "lucide-react";

const claimRows = [
  {
    icon: CheckCircle,
    color: "text-emerald-500 dark:text-emerald-400",
    text: "Verified — Nature 2024 retraction archive",
  },
  {
    icon: XCircle,
    color: "text-red-500 dark:text-red-400",
    text: "False — citation 7 doesn't support claim",
  },
  {
    icon: Brain,
    color: "text-amber-500 dark:text-amber-400",
    text: "AI-likely — paragraphs 3, 5, 11 (>0.7)",
  },
];

/** Word-by-word mask reveal. Each word in an `overflow-hidden` span,
 *  slides up 110% to 0. Stagger 50ms. Honors reduced-motion via duration:0
 *  (initial state stays invariant for SSR safety). */
function HeadlineWords({
  segments,
  reduce,
}: {
  segments: { text: string; emphasis?: boolean }[];
  reduce: boolean;
}) {
  let wordIndex = 0;
  return (
    <>
      {segments.map((seg, segIdx) => {
        const words = seg.text.split(" ");
        return (
          <span
            key={segIdx}
            className={
              seg.emphasis
                ? "italic text-brand-fg dark:text-brand-fg"
                : undefined
            }
          >
            {words.map((word, i) => {
              const idx = wordIndex++;
              return (
                <span
                  key={`${segIdx}-${i}`}
                  className="inline-block overflow-hidden align-bottom pb-[0.05em]"
                >
                  <motion.span
                    className="inline-block"
                    initial={{ y: "110%" }}
                    animate={{ y: 0 }}
                    transition={{
                      duration: reduce ? 0 : 0.55,
                      delay: reduce ? 0 : 0.1 + idx * 0.05,
                      ease: [0.16, 1, 0.3, 1],
                    }}
                  >
                    {word}
                  </motion.span>
                  {i < words.length - 1 ? " " : ""}
                </span>
              );
            })}
            {segIdx < segments.length - 1 ? " " : ""}
          </span>
        );
      })}
    </>
  );
}

export function HeroSection() {
  const reduce = useReducedMotion();

  const fade = (delay: number) => ({
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    transition: {
      duration: reduce ? 0 : 0.5,
      delay: reduce ? 0 : delay,
      ease: [0.16, 1, 0.3, 1] as const,
    },
  });

  return (
    <section className="relative flex min-h-[100dvh] items-center overflow-hidden pt-20 md:pt-0">
      {/* Backdrop: a single warm wine glow off-center, low opacity, no
          grid pattern, no mesh. Plays in both light and dark via the
          brand token. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
      >
        <div
          className="absolute -top-1/4 left-1/2 h-[80vh] w-[80vh] -translate-x-1/2 rounded-full blur-[160px]"
          style={{ background: "color-mix(in oklab, var(--brand) 22%, transparent)" }}
        />
      </div>

      <div className="relative mx-auto w-full max-w-7xl px-6 py-16">
        <div className="grid grid-cols-1 items-center gap-16 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
          {/* Left — Copy + CTA */}
          <div>
            <motion.p
              {...fade(0)}
              className="inline-flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-brand-fg"
            >
              <Sparkle className="h-3 w-3" strokeWidth={1.5} aria-hidden="true" />
              Research integrity, automated
            </motion.p>

            <h1 className="mt-6 font-display text-5xl font-semibold leading-[1.02] tracking-tight text-balance text-fg-primary sm:text-6xl md:text-7xl lg:text-[5.25rem]">
              <HeadlineWords
                segments={[
                  { text: "Know if you can" },
                  { text: "trust the research.", emphasis: true },
                ]}
                reduce={Boolean(reduce)}
              />
            </h1>

            <motion.p
              {...fade(0.3)}
              className="mt-7 max-w-xl text-lg leading-relaxed text-fg-secondary sm:text-xl"
            >
              Five integrity engines on one submission — plagiarism, AI
              detection, citation rings, fact-checking, researcher
              scoring. Every score breaks down to a list of specific
              deductions you can defend in writing.
            </motion.p>

            <motion.div
              {...fade(0.45)}
              className="mt-9 flex flex-col items-start gap-4 sm:flex-row sm:items-center"
            >
              <Link
                href="/register"
                className="cta-glow group inline-flex h-13 items-center justify-center gap-2 rounded-xl bg-brand px-7 py-3 text-base font-semibold text-white shadow-lg shadow-[color:var(--brand)]/25 transition-all hover:bg-brand-hover active:translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
              >
                Start free analysis
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" strokeWidth={2} />
              </Link>
              <Link
                href="#how-it-works"
                className="inline-flex h-13 items-center justify-center rounded-xl border border-border-default bg-transparent px-6 py-3 text-base font-medium text-fg-primary transition-colors hover:bg-surface-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
              >
                See it in action
              </Link>
            </motion.div>

            <motion.p
              {...fade(0.6)}
              className="mt-5 text-xs text-fg-tertiary"
            >
              No credit card · 10 free checks per month
            </motion.p>

            <motion.div {...fade(0.75)} className="mt-10 max-w-xl">
              <div className="flex items-start gap-3 rounded-lg border border-border-default bg-surface-card px-4 py-3">
                <span
                  aria-hidden="true"
                  className="mt-1.5 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-brand"
                />
                <p className="text-sm leading-relaxed text-fg-secondary">
                  <span className="font-medium text-fg-primary">
                    Pre-launch in the EaP region.
                  </span>{" "}
                  Built for 51 universities and 222,809 students across
                  Azerbaijan and the Eastern Partnership.
                </p>
              </div>
            </motion.div>
          </div>

          {/* Right — Product mockup */}
          <motion.div {...fade(0.55)} className="relative">
            <div className="relative overflow-hidden rounded-2xl border border-border-default bg-surface-card shadow-[0_30px_60px_-20px_rgba(124,40,40,0.25)] dark:shadow-[0_30px_60px_-20px_rgba(0,0,0,0.6)]">
              {/* Browser chrome */}
              <div className="flex items-center gap-1.5 border-b border-border-subtle bg-surface-elevated px-4 py-3">
                <div className="h-2.5 w-2.5 rounded-full bg-red-500/60" />
                <div className="h-2.5 w-2.5 rounded-full bg-amber-500/60" />
                <div className="h-2.5 w-2.5 rounded-full bg-emerald-500/60" />
                <span className="ml-3 truncate font-mono text-xs text-fg-tertiary">
                  app.example.invalid/check/results
                </span>
              </div>

              <div className="space-y-4 p-5">
                <div className="flex items-center gap-3">
                  <div
                    aria-hidden="true"
                    className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-[3px] border-emerald-500 text-emerald-500 dark:text-emerald-400"
                  >
                    <span className="font-display text-lg font-bold tabular-nums">
                      92
                    </span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-fg-primary">
                      A Review of Climate Sensitivity Estimates (2024)
                    </p>
                    <p className="text-xs text-fg-tertiary">
                      Credibility: high · 2 minor issues
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  {claimRows.map((row, i) => {
                    const Icon = row.icon;
                    return (
                      <div
                        key={i}
                        className="flex items-start gap-2.5 rounded-md border border-border-subtle bg-surface-base px-3 py-2"
                      >
                        <Icon
                          className={`mt-0.5 h-4 w-4 shrink-0 ${row.color}`}
                          strokeWidth={2}
                          aria-hidden="true"
                        />
                        <p className="text-xs text-fg-primary">{row.text}</p>
                      </div>
                    );
                  })}
                </div>

                <div>
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="text-xs font-medium text-fg-secondary">
                      AI-likely content
                    </span>
                    <span className="text-xs tabular-nums text-fg-tertiary">14%</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-border-subtle">
                    <div
                      className="h-full rounded-full bg-emerald-500"
                      style={{ width: "14%" }}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Floating credibility ribbon */}
            <div className="absolute -bottom-4 -left-4 hidden rounded-lg border border-border-default bg-surface-card px-3 py-2 shadow-lg sm:flex">
              <div className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-brand-soft"
                >
                  <span className="font-display text-xs font-bold text-brand-fg">3</span>
                </span>
                <div>
                  <p className="text-xs font-semibold text-fg-primary">
                    Verified by 3 sources
                  </p>
                  <p className="font-mono text-[10px] text-fg-tertiary">
                    NOAA · Nature · arXiv
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
