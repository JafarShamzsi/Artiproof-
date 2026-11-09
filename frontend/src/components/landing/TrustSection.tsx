"use client";

import { motion, useReducedMotion } from "framer-motion";

interface Stat {
  /** Footnote-style superscript label — 1, 2, 3, 4 (rendered in mono). */
  mark: string;
  value: string;
  label: string;
  source: string;
}

const stats: Stat[] = [
  {
    mark: "1",
    value: "14,000",
    label: "Retractions detected each year",
    source: "Retraction Watch · 2024",
  },
  {
    mark: "2",
    value: "92%",
    label: "Students using AI writing tools",
    source: "HEPI Survey · 2024",
  },
  {
    mark: "3",
    value: "$392K",
    label: "Mean cost of a retracted paper",
    source: "eLife · 2024",
  },
  {
    mark: "4",
    value: "<2 min",
    label: "Time to a full reading",
    source: "ArtiProof · telemetry",
  },
];

/** A sourced ledger. Each stat has a footnote-style superscript the
 *  way a research paper labels its references. The set is bracketed by
 *  doubled hairline rules and titled with a small-caps editorial label. */
export function TrustSection() {
  const reduce = useReducedMotion();

  return (
    <section className="border-y border-border-subtle py-20 sm:py-24">
      <div className="mx-auto max-w-6xl px-6">
        {/* Editorial label */}
        <div className="mb-10 flex items-center gap-3">
          <span aria-hidden="true" className="h-px w-7 bg-border-strong" />
          <span className="label-eyebrow text-brand-fg">
            Findings of fact
          </span>
          <span aria-hidden="true" className="h-px flex-1 bg-border-strong" />
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-fg-tertiary">
            §
          </span>
        </div>

        <div className="grid grid-cols-2 gap-x-10 gap-y-12 md:grid-cols-4">
          {stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: reduce ? 0 : 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{
                duration: reduce ? 0 : 0.55,
                delay: reduce ? 0 : i * 0.08,
                ease: [0.16, 1, 0.3, 1],
              }}
              className="relative"
            >
              {/* Faint vertical hairline between columns on desktop. */}
              {i !== 0 && (
                <span
                  aria-hidden="true"
                  className="absolute -left-5 top-1 hidden h-12 w-px bg-border-default md:block"
                />
              )}

              <div className="flex items-baseline gap-1.5">
                <span className="font-display text-5xl font-semibold leading-none tracking-[-0.02em] tabular-nums text-fg-primary md:text-[3.5rem]">
                  {stat.value}
                </span>
                <span className="footnote-mark">{stat.mark}</span>
              </div>

              <p className="mt-3 max-w-[14rem] font-display text-base font-medium leading-snug text-fg-primary">
                {stat.label}
              </p>

              <p className="mt-2 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-fg-tertiary">
                <span className="footnote-mark !text-fg-tertiary">
                  {stat.mark}
                </span>
                {stat.source}
              </p>
            </motion.div>
          ))}
        </div>

        {/* Editorial sign-off line. */}
        <p className="editorial-italic mt-12 max-w-2xl border-t border-border-subtle pt-6 text-sm text-fg-tertiary">
          Numbers are recorded findings, not estimates. Each citation is
          preserved in the published report so a reader can re-trace
          the chain themselves.
        </p>
      </div>
    </section>
  );
}
