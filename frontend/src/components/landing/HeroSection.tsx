"use client";

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";
import {
  ArrowRight,
  Brain,
  CheckCircle,
  Shield,
  XCircle,
} from "lucide-react";

const claimRows = [
  {
    icon: CheckCircle,
    color: "text-emerald-400",
    text: "Verified — Nature 2024 retraction archive",
  },
  {
    icon: XCircle,
    color: "text-red-400",
    text: "False — citation 7 doesn't support claim",
  },
  {
    icon: Brain,
    color: "text-amber-400",
    text: "AI-likely — paragraphs 3, 5, 11 (>0.7)",
  },
];

export function HeroSection() {
  const reduce = useReducedMotion();

  const fade = (delay: number) => ({
    initial: { opacity: 0, y: reduce ? 0 : 20 },
    animate: { opacity: 1, y: 0 },
    transition: {
      duration: reduce ? 0 : 0.5,
      delay: reduce ? 0 : delay,
      ease: [0.16, 1, 0.3, 1] as const,
    },
  });

  return (
    <section className="relative flex min-h-screen items-center overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-zinc-950 via-zinc-950 to-zinc-900/40" />

      <div className="relative mx-auto w-full max-w-7xl px-6 py-20">
        <div className="grid grid-cols-1 items-center gap-16 lg:grid-cols-2">
          {/* Left — Copy + CTA */}
          <div>
            <motion.p
              {...fade(0)}
              className="text-xs font-medium uppercase tracking-wider text-emerald-400"
            >
              Research integrity, automated
            </motion.p>

            <motion.h1
              {...fade(0.1)}
              className="mt-6 font-display text-4xl font-bold leading-[1.05] tracking-tight text-white sm:text-5xl md:text-6xl lg:text-7xl"
            >
              Know if you can{" "}
              <span className="text-emerald-400">trust the research</span>.
            </motion.h1>

            <motion.p
              {...fade(0.25)}
              className="mt-6 max-w-xl text-lg text-zinc-400 sm:text-xl"
            >
              Five integrity checks in one platform — AI detection, plagiarism,
              citation rings, fact-checking, and researcher scoring. Built for
              universities across Azerbaijan and the EaP region.
            </motion.p>

            <motion.div
              {...fade(0.4)}
              className="mt-8 flex flex-col items-start gap-3"
            >
              <Link
                href="/register"
                className="cta-glow group inline-flex h-14 items-center justify-center gap-2 rounded-xl bg-emerald-500 px-8 text-base font-semibold text-white shadow-lg shadow-emerald-500/25 transition-all hover:bg-emerald-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50"
              >
                Start free analysis
                <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <p className="text-xs text-zinc-500">
                No credit card required · 10 free checks per month
              </p>
            </motion.div>

            {/* Honest pre-launch trust line — no fake star ratings.
                Real signal: scope of the launch + the audited number that
                anchors the comparison section. */}
            <motion.div {...fade(0.55)} className="mt-10 max-w-xl">
              <div className="flex items-start gap-3 rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-3">
                <Shield className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" aria-hidden="true" />
                <p className="text-sm leading-relaxed text-zinc-400">
                  <span className="font-medium text-zinc-200">
                    Pre-launch in the EaP region.
                  </span>{" "}
                  Built for 51 universities and 222,809 students across
                  Azerbaijan and the Eastern Partnership.
                </p>
              </div>
            </motion.div>
          </div>

          {/* Right — Product browser mockup */}
          <motion.div
            {...fade(0.5)}
            className="relative"
          >
            <div className="relative overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900 shadow-2xl shadow-black/50">
              {/* Browser chrome */}
              <div className="flex items-center gap-1.5 border-b border-zinc-800 px-4 py-3">
                <div className="h-3 w-3 rounded-full bg-red-500/60" />
                <div className="h-3 w-3 rounded-full bg-yellow-500/60" />
                <div className="h-3 w-3 rounded-full bg-green-500/60" />
                <span className="ml-3 truncate text-xs text-zinc-500">
                  app.example.invalid/check/results
                </span>
              </div>

              {/* Mock results page */}
              <div className="space-y-4 p-5">
                <div className="flex items-center gap-3">
                  <div
                    className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-3 border-emerald-500 text-emerald-400"
                    aria-hidden="true"
                  >
                    <span className="text-lg font-bold">92</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-white">
                      A Review of Climate Sensitivity Estimates (2024)
                    </p>
                    <p className="text-xs text-zinc-500">
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
                        className="flex items-start gap-2.5 rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2"
                      >
                        <Icon
                          className={`mt-0.5 h-4 w-4 shrink-0 ${row.color}`}
                          aria-hidden="true"
                        />
                        <p className="text-xs text-zinc-300">{row.text}</p>
                      </div>
                    );
                  })}
                </div>

                {/* AI bar mock */}
                <div>
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="text-xs font-medium text-zinc-400">
                      AI-likely content
                    </span>
                    <span className="text-xs text-zinc-500">14%</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-zinc-800">
                    <div
                      className="h-full rounded-full bg-emerald-500"
                      style={{ width: "14%" }}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Floating credibility badge */}
            <div className="absolute -bottom-4 -left-4 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 shadow-xl">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/20">
                  <Shield className="h-4 w-4 text-emerald-400" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-white">High confidence</p>
                  <p className="text-[10px] text-zinc-500">Verified by 3 sources</p>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
