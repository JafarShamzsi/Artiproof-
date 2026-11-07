"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight } from "lucide-react";

export function CTASection() {
  const reduce = useReducedMotion();

  return (
    <section className="relative overflow-hidden px-6 py-32 sm:py-36">
      {/* Backdrop wash — wine glow centered, aged-paper warmth at corners */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10"
      >
        <div
          className="absolute left-1/2 top-1/2 h-[80vh] w-[80vh] -translate-x-1/2 -translate-y-1/2 rounded-full blur-[180px]"
          style={{
            background:
              "color-mix(in oklab, var(--brand) 18%, transparent)",
          }}
        />
      </div>

      <div className="relative mx-auto max-w-4xl text-center">
        {/* Coda heading */}
        <motion.div
          initial={{ opacity: 0, y: reduce ? 0 : 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: reduce ? 0 : 0.55, ease: [0.16, 1, 0.3, 1] }}
          className="flex items-center justify-center gap-3"
        >
          <span aria-hidden="true" className="h-px w-7 bg-border-strong" />
          <span className="label-eyebrow text-brand-fg">
            § Coda · An invitation
          </span>
          <span aria-hidden="true" className="h-px w-7 bg-border-strong" />
        </motion.div>

        <motion.h2
          initial={{ opacity: 0, y: reduce ? 0 : 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{
            duration: reduce ? 0 : 0.6,
            delay: reduce ? 0 : 0.1,
            ease: [0.16, 1, 0.3, 1],
          }}
          className="mt-7 font-display text-5xl font-semibold leading-[1.02] tracking-[-0.02em] text-balance text-fg-primary sm:text-[3.5rem] md:text-[4.25rem]"
        >
          Begin a reading in{" "}
          <span className="italic text-brand-fg">ninety seconds.</span>
        </motion.h2>

        <motion.p
          initial={{ opacity: 0, y: reduce ? 0 : 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{
            duration: reduce ? 0 : 0.55,
            delay: reduce ? 0 : 0.22,
            ease: [0.16, 1, 0.3, 1],
          }}
          className="editorial-italic mx-auto mt-6 max-w-xl text-lg text-fg-secondary sm:text-xl"
        >
          Free for the first ten readings. No credit card. No commitment.
          Bring a paper, a URL, or a paragraph.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: reduce ? 0 : 14 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{
            duration: reduce ? 0 : 0.55,
            delay: reduce ? 0 : 0.34,
            ease: [0.16, 1, 0.3, 1],
          }}
          className="mt-12 flex flex-col items-center gap-4"
        >
          <Link
            href="/register"
            className="cta-glow group inline-flex h-14 items-center justify-center gap-2 rounded-sm bg-brand px-9 text-base font-semibold text-white shadow-[0_12px_30px_-10px_color-mix(in_oklab,var(--brand)_60%,transparent)] transition-all hover:bg-brand-hover active:translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
          >
            Begin a reading
            <ArrowRight
              className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
              strokeWidth={2}
            />
          </Link>
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-fg-tertiary">
            No credit card · 10 readings / month · Cancel anytime
          </p>
        </motion.div>

        {/* Editorial sign-off — looks like a hand-set type ornament */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{
            duration: reduce ? 0 : 0.7,
            delay: reduce ? 0 : 0.5,
            ease: [0.16, 1, 0.3, 1],
          }}
          className="mt-20 flex items-center justify-center gap-3"
        >
          <span aria-hidden="true" className="h-px w-12 bg-border-default" />
          <span className="font-display text-lg italic text-brand-fg">
            ❦
          </span>
          <span aria-hidden="true" className="h-px w-12 bg-border-default" />
        </motion.div>

        <p className="editorial-italic mt-6 text-sm text-fg-tertiary">
          Built for researchers across ADA University, Baku State
          University, and Khazar University.
        </p>
      </div>
    </section>
  );
}
