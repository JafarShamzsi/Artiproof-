"use client";

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { StampBadge } from "@/components/landing/shared/StampBadge";

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
                <span key={`${segIdx}-${i}`}>
                  <span className="inline-block overflow-hidden align-bottom pb-[0.05em]">
                    <motion.span
                      className="inline-block"
                      initial={{ y: "110%" }}
                      animate={{ y: 0 }}
                      transition={{
                        duration: reduce ? 0 : 0.62,
                        delay: reduce ? 0 : 0.18 + idx * 0.05,
                        ease: [0.16, 1, 0.3, 1],
                      }}
                    >
                      {word}
                    </motion.span>
                  </span>
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

/** ───────────────────────────────────────────────────────────────────
 *  HeroSection — "Annotated Manuscript"
 *
 *  The right column is no longer a browser mockup but a paper page
 *  with editorial body text and three marginal verdict annotations
 *  tied to specific lines. A circular "92 Credibility" stamp lands
 *  rotated at the top corner. The left column carries the editorial
 *  kicker, headline, drop-cap body, and CTA pair.
 *  ─────────────────────────────────────────────────────────────────── */
export function HeroSection() {
  const reduce = useReducedMotion();

  const fade = (delay: number) => ({
    initial: { opacity: 0, y: reduce ? 0 : 16 },
    animate: { opacity: 1, y: 0 },
    transition: {
      duration: reduce ? 0 : 0.5,
      delay: reduce ? 0 : delay,
      ease: [0.16, 1, 0.3, 1] as const,
    },
  });

  return (
    <section className="relative flex min-h-[100dvh] items-center overflow-hidden pt-24 md:pt-0">
      {/* Backdrop: a single warm wine glow off-center, low opacity. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
      >
        <div
          className="absolute -top-1/3 left-[58%] h-[90vh] w-[90vh] -translate-x-1/2 rounded-full blur-[180px]"
          style={{ background: "color-mix(in oklab, var(--brand) 22%, transparent)" }}
        />
        <div
          className="absolute -bottom-1/3 -left-20 h-[60vh] w-[60vh] rounded-full blur-[160px]"
          style={{ background: "color-mix(in oklab, var(--accent-amber) 8%, transparent)" }}
        />
      </div>

      <div className="relative mx-auto w-full max-w-7xl px-6 py-12 md:py-20">
        <div className="grid grid-cols-1 items-center gap-x-12 gap-y-20 lg:grid-cols-[minmax(0,1.04fr)_minmax(0,1fr)]">
          {/* ─── Left — editorial kicker, headline, body, CTA ─── */}
          <div className="relative">
            {/* Edition kicker — small caps, hairline rule, dateline. */}
            <motion.div
              {...fade(0)}
              className="flex items-center gap-3"
            >
              <span aria-hidden="true" className="h-px w-7 bg-border-strong" />
              <span className="label-eyebrow text-brand-fg">
                Edition I · Spring 2026
              </span>
            </motion.div>

            <h1 className="mt-7 font-display text-5xl font-semibold leading-[0.98] tracking-[-0.02em] text-balance text-fg-primary sm:text-6xl md:text-[5.25rem] lg:text-[5.75rem]">
              <HeadlineWords
                segments={[
                  { text: "Know if you can" },
                  { text: "trust", emphasis: true },
                  { text: "the research." },
                ]}
                reduce={Boolean(reduce)}
              />
            </h1>

            {/* Italic editorial subtitle — a literary "thesis" line. */}
            <motion.p
              {...fade(0.32)}
              className="editorial-italic mt-7 max-w-xl text-xl leading-relaxed sm:text-2xl"
            >
              A clear-eyed reading of every paper, claim, and citation —
              with the deductions written out beside the score.
            </motion.p>

            {/* Drop-cap body — first body paragraph leads with a dropped
                Fraunces capital, the way a journal article opens. */}
            <motion.div
              {...fade(0.46)}
              className="drop-cap measure mt-9 text-base leading-[1.7] text-fg-primary sm:text-[17px]"
            >
              Five integrity engines on one submission — plagiarism, AI
              detection, citation rings, fact-checking, researcher
              scoring. Every score breaks down to a list of specific
              deductions. No black box. No mystery weighting. The number
              you see is the sum of recorded findings, each with a
              source attached.
            </motion.div>

            {/* CTA pair */}
            <motion.div
              {...fade(0.62)}
              className="mt-10 flex flex-col items-start gap-4 sm:flex-row sm:items-center"
            >
              <Link
                href="/register"
                className="cta-glow group inline-flex h-13 items-center justify-center gap-2 rounded-sm bg-brand px-7 py-3.5 text-base font-semibold text-white shadow-[0_8px_24px_-8px_color-mix(in_oklab,var(--brand)_60%,transparent)] transition-all hover:bg-brand-hover active:translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
              >
                Begin a reading
                <ArrowRight
                  className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
                  strokeWidth={2}
                />
              </Link>
              <Link
                href="#how-it-works"
                className="group inline-flex h-13 items-center justify-center gap-2 px-2 py-3.5 text-base font-medium text-fg-primary transition-colors focus-visible:outline-none"
              >
                <span className="ink-underline">See how a finding reads</span>
                <ArrowRight
                  className="h-3.5 w-3.5 -translate-x-0.5 opacity-60 transition-all group-hover:translate-x-0 group-hover:opacity-100"
                  strokeWidth={1.75}
                />
              </Link>
            </motion.div>

            <motion.p
              {...fade(0.74)}
              className="mt-5 font-mono text-[11px] uppercase tracking-wider text-fg-tertiary"
            >
              No credit card · 10 free readings per month
            </motion.p>
          </div>

          {/* ─── Right — annotated paper spread ─── */}
          <motion.div
            {...fade(0.55)}
            className="relative"
          >
            <PaperSpread />
          </motion.div>
        </div>

        {/* Bottom dateline / regional commitment — typographic colophon
            sitting beneath the hero spread, separated by a doubled rule. */}
        <motion.div
          {...fade(0.9)}
          className="mt-20 grid grid-cols-1 gap-y-8 border-t border-border-subtle pt-8 sm:grid-cols-[auto_1fr_auto] sm:gap-x-10"
        >
          <div className="flex items-center gap-3">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-brand" />
            <span className="label-eyebrow text-brand-fg">
              Pre-launch · Eastern Partnership
            </span>
          </div>
          <p className="editorial-italic text-sm leading-relaxed text-fg-secondary sm:text-base">
            Built for{" "}
            <span className="font-mono text-[0.92em] tracking-tight text-fg-primary">
              51
            </span>{" "}
            universities and{" "}
            <span className="font-mono text-[0.92em] tracking-tight text-fg-primary">
              222,809
            </span>{" "}
            students across Azerbaijan and the Eastern Partnership region.
          </p>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-fg-tertiary">
            ADA · BSU · Khazar
          </p>
        </motion.div>
      </div>
    </section>
  );
}

/** The annotated paper spread shown in the hero's right column. A paper
 *  page with title, authors, abstract, body excerpt — and three margin
 *  verdicts in italic Newsreader connected to the body by hairline
 *  brackets. A circular credibility stamp lands at the top corner. */
function PaperSpread() {
  const reduce = useReducedMotion();

  // Body line index for each marginal annotation.
  // The connector line height (12% per body line) is fragile but visual,
  // so we keep absolute positions tuned to the rendered paragraphs below.
  const annotations = [
    {
      label: "Verdict",
      text: "Verified — Nature 2024 retraction archive.",
      tone: "emerald" as const,
      top: "20%",
      delay: 0.95,
    },
    {
      label: "Citation",
      text: "Reference 7 doesn't support the claim.",
      tone: "red" as const,
      top: "44%",
      delay: 1.15,
    },
    {
      label: "AI signal",
      text: "Paragraphs 3, 5, 11 — likelihood >0.7.",
      tone: "amber" as const,
      top: "68%",
      delay: 1.35,
    },
  ];

  const toneClass = {
    emerald: "text-emerald-700 dark:text-emerald-300",
    red: "text-red-700 dark:text-red-300",
    amber: "text-amber-700 dark:text-amber-300",
  };
  const toneDot = {
    emerald: "bg-emerald-500",
    red: "bg-red-500",
    amber: "bg-amber-500",
  };

  return (
    <div className="relative">
      {/* Faint paper shadow stack — gives the page a sense of weight. */}
      <div
        aria-hidden="true"
        className="absolute inset-0 -translate-y-2 translate-x-2 rotate-[1.2deg] rounded-sm border border-border-subtle bg-surface-card/40 shadow-[0_30px_60px_-25px_color-mix(in_oklab,var(--brand)_28%,transparent)]"
      />
      <div
        aria-hidden="true"
        className="absolute inset-0 translate-y-1 -translate-x-1 -rotate-[0.6deg] rounded-sm border border-border-subtle bg-surface-card/60"
      />

      {/* Main paper page */}
      <div className="relative grid grid-cols-[1fr_auto] gap-3 rounded-sm border border-border-default bg-surface-card p-7 shadow-[0_40px_80px_-30px_color-mix(in_oklab,var(--brand)_35%,transparent)] sm:p-9">
        {/* Body column */}
        <div className="relative min-w-0">
          {/* Catalog header */}
          <div className="flex items-center justify-between gap-3 border-b border-border-default pb-3">
            <span className="label-eyebrow text-fg-tertiary">Manuscript №</span>
            <span className="font-mono text-[11px] tracking-wider text-fg-tertiary">
              AP–2024–0047
            </span>
          </div>

          {/* Title */}
          <h3 className="mt-5 font-display text-[1.35rem] font-semibold leading-tight text-fg-primary sm:text-[1.55rem]">
            A Review of Climate Sensitivity Estimates
          </h3>
          <p className="editorial-italic mt-2 text-sm text-fg-secondary">
            Yusifova, A. · Asadov, R. · 2024
          </p>

          <hr className="rule-hair my-5" />

          {/* Body excerpt — an "abstract"-style paragraph that the
              marginal annotations point at. Each line index is what
              the marginalia top% targets. */}
          <p className="text-[13px] leading-[1.85] text-fg-primary sm:text-sm">
            <span className="font-display text-[1.6em] font-semibold leading-[0.6] text-brand-fg">
              W
            </span>
            e revisit equilibrium climate sensitivity using the latest
            instrumental temperature record alongside the published
            paleoclimate constraints. Compared with the Sherwood et al.
            synthesis, our estimate narrows the lower tail by an order
            of magnitude. We attribute the shift to two factors. First,
            the corrected sea-surface temperature reanalysis removes a
            systematic cooling bias[<span className="text-brand-fg">7</span>].
            Second, the revised aerosol forcing budget brings the
            short-wave cloud feedback into the range reported by
            CESM2-WACCM and HadGEM3. The combined effect repositions
            the central estimate at 3.1 K with a 90% range of 2.4 to
            4.0 K, consistent with the IPCC AR6 likely range.
          </p>

          {/* Footnote rule + small footer */}
          <hr className="rule-hair my-5" />
          <p className="font-mono text-[10px] tracking-wider text-fg-tertiary">
            Excerpt — full report available after analysis.
          </p>
        </div>

        {/* ─── Right margin (visible at xl+ where the paper has room
             for it; below xl, the marginalia falls inline beneath the
             body excerpt). The vertical positions below are decorative
             — calibrated to the abstract's natural line-rhythm at typical
             desktop widths. ─── */}
        <div className="relative hidden w-44 shrink-0 xl:block">
          {annotations.map((a, i) => (
            <motion.div
              key={i}
              initial={
                reduce ? { opacity: 1, x: 0 } : { opacity: 0, x: -8 }
              }
              animate={{ opacity: 1, x: 0 }}
              transition={{
                duration: reduce ? 0 : 0.5,
                delay: reduce ? 0 : a.delay,
                ease: [0.16, 1, 0.3, 1],
              }}
              style={{ top: a.top }}
              className="absolute left-0 right-0"
            >
              <div className="flex items-start gap-2">
                <span
                  aria-hidden="true"
                  className="connector-bracket mt-2 shrink-0"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-1.5">
                    <span
                      aria-hidden="true"
                      className={`h-1.5 w-1.5 shrink-0 rounded-full ${toneDot[a.tone]}`}
                    />
                    <span className="label-eyebrow text-fg-tertiary">
                      {a.label}
                    </span>
                  </div>
                  <p
                    className={`editorial-italic mt-1 text-[13px] leading-snug ${toneClass[a.tone]}`}
                  >
                    {a.text}
                  </p>
                </div>
              </div>
            </motion.div>
          ))}
        </div>

        {/* ─── Fallback (below xl): marginalia inline under the body so
             it stays connected to the verdict idea even on tighter
             viewports where there's no room for a true margin. ─── */}
        <div className="col-span-2 mt-3 space-y-2 border-t border-border-subtle pt-4 xl:hidden">
          {annotations.map((a, i) => (
            <div key={i} className="flex items-start gap-2">
              <span
                aria-hidden="true"
                className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${toneDot[a.tone]}`}
              />
              <div>
                <span className="label-eyebrow text-fg-tertiary">
                  {a.label}
                </span>
                <p
                  className={`editorial-italic text-sm leading-snug ${toneClass[a.tone]}`}
                >
                  {a.text}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Top-right credibility stamp — lands rotated, sits half over the
          paper edge so it reads as a stamp on top of the page. */}
      <div className="absolute -right-3 -top-5 z-10 sm:-right-6 sm:-top-7">
        <motion.div
          initial={
            reduce
              ? { opacity: 1, scale: 1, rotate: -8 }
              : { opacity: 0, scale: 1.4, rotate: 0 }
          }
          animate={{ opacity: 1, scale: 1, rotate: -8 }}
          transition={{
            duration: reduce ? 0 : 0.6,
            delay: reduce ? 0 : 1.05,
            ease: [0.16, 1, 0.3, 1],
          }}
        >
          <StampBadge shape="circle" tone="wine" animate={false} size={92}>
            <div className="flex flex-col items-center leading-none">
              <span className="font-display text-[1.85rem] font-bold tabular-nums leading-none">
                92
              </span>
              <span className="mt-1 text-[8px] tracking-[0.18em]">CRED.</span>
            </div>
          </StampBadge>
        </motion.div>
      </div>

      {/* Bottom-left exhibit tag — a small ribbon labeling this
          mockup as "Exhibit A" the way a forensic file would. */}
      <motion.div
        initial={
          reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }
        }
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: reduce ? 0 : 0.5,
          delay: reduce ? 0 : 1.2,
          ease: [0.16, 1, 0.3, 1],
        }}
        className="absolute -bottom-3 -left-2 hidden -rotate-2 items-center gap-2 rounded-sm border border-border-strong bg-surface-base px-3 py-1.5 shadow-md sm:flex"
      >
        <span
          aria-hidden="true"
          className="h-1 w-1 rounded-full bg-brand"
        />
        <span className="label-eyebrow text-brand-fg">Exhibit A</span>
        <span className="font-mono text-[10px] text-fg-tertiary">·</span>
        <span className="editorial-italic text-xs text-fg-secondary">
          a worked example
        </span>
      </motion.div>
    </div>
  );
}
