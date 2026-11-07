"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import { SectionHeading } from "@/components/landing/shared/SectionHeading";
import { ScrollReveal } from "@/components/landing/shared/ScrollReveal";
import { EngineGrid } from "@/components/landing/EngineGrid";

type ScanState = "idle" | "scanning" | "complete";

const exampleClaims = [
  "COVID vaccines contain microchips",
  "5G towers cause cancer",
  "The election was stolen",
] as const;

const threatScores: Record<string, number> = {
  "COVID vaccines contain microchips": 87,
  "5G towers cause cancer": 82,
  "The election was stolen": 91,
};

const disarmTags = [
  { id: "T0023", label: "Distort Facts" },
  { id: "T0049", label: "Flooding" },
];

export function ScannerPreview() {
  const [input, setInput] = useState("");
  const [state, setState] = useState<ScanState>("idle");
  const [progress, setProgress] = useState(0);
  const [activeClaim, setActiveClaim] = useState("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cleanup = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    return cleanup;
  }, [cleanup]);

  const startScan = useCallback(
    (claim: string) => {
      cleanup();
      setActiveClaim(claim);
      setInput(claim);
      setProgress(0);

      timeoutRef.current = setTimeout(() => {
        setState("scanning");

        const totalDuration = 2500;
        const steps = 50;
        const stepDuration = totalDuration / steps;
        let currentStep = 0;

        intervalRef.current = setInterval(() => {
          currentStep++;
          setProgress((currentStep / steps) * 100);

          if (currentStep >= steps) {
            if (intervalRef.current) {
              clearInterval(intervalRef.current);
              intervalRef.current = null;
            }
            setState("complete");
          }
        }, stepDuration);
      }, 300);
    },
    [cleanup]
  );

  const handleReset = useCallback(() => {
    cleanup();
    setState("idle");
    setInput("");
    setActiveClaim("");
    setProgress(0);
  }, [cleanup]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (input.trim() && state === "idle") {
        startScan(input.trim());
      }
    },
    [input, state, startScan]
  );

  const threatScore = threatScores[activeClaim] ?? 85;

  return (
    <section id="scanner" className="py-24">
      <div className="mx-auto max-w-4xl px-6">
        <SectionHeading
          eyebrow="LIVE DEMO"
          title="See It In Action"
          gradient="Action"
        />

        <ScrollReveal>
          {/* Input area */}
          <AnimatePresence mode="wait">
            {state === "idle" && (
              <motion.div
                key="idle"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3 }}
              >
                <form onSubmit={handleSubmit}>
                  <div className="relative">
                    <input
                      type="text"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      placeholder="Paste a claim to analyze..."
                      className="w-full rounded-xl border border-zinc-700/50 bg-zinc-900 p-4 pr-14 text-white placeholder-zinc-500 outline-none transition-colors focus:border-emerald-500/50"
                    />
                    <button
                      type="submit"
                      className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg bg-emerald-500 p-2 text-white transition-all hover:bg-emerald-600 hover:shadow-lg hover:shadow-emerald-500/20"
                    >
                      <Search className="size-4" />
                    </button>
                  </div>
                </form>

                {/* Example pills */}
                <div className="mt-4 flex flex-wrap gap-2">
                  {exampleClaims.map((claim) => (
                    <button
                      key={claim}
                      type="button"
                      onClick={() => startScan(claim)}
                      className="cursor-pointer rounded-full border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400 transition hover:border-emerald-500/50 hover:text-emerald-400"
                    >
                      {claim}
                    </button>
                  ))}
                </div>
              </motion.div>
            )}

            {state === "scanning" && (
              <motion.div
                key="scanning"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3 }}
                className="space-y-6"
              >
                {/* Claim being analyzed */}
                <div className="rounded-xl border border-zinc-700/50 bg-zinc-900 p-4">
                  <p className="text-sm text-zinc-400">Analyzing:</p>
                  <p className="mt-1 font-medium text-white">{activeClaim}</p>
                </div>

                {/* Progress bar */}
                <div className="space-y-3">
                  <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-800">
                    <motion.div
                      className="h-full rounded-full bg-emerald-500"
                      style={{ width: `${progress}%` }}
                      transition={{ duration: 0.05 }}
                    />
                  </div>
                  <p className="text-center text-sm text-zinc-400">
                    Analyzing with 6 engines...
                  </p>
                </div>
              </motion.div>
            )}

            {state === "complete" && (
              <motion.div
                key="complete"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3 }}
                className="space-y-6"
              >
                {/* Claim analyzed */}
                <div className="rounded-xl border border-zinc-700/50 bg-zinc-900 p-4">
                  <p className="text-sm text-zinc-400">Claim analyzed:</p>
                  <p className="mt-1 font-medium text-white">{activeClaim}</p>
                </div>

                {/* Threat score + DISARM tags */}
                <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center sm:gap-8">
                  {/* Circular threat score gauge */}
                  <div className="relative flex h-28 w-28 shrink-0 items-center justify-center">
                    <svg
                      className="absolute inset-0 h-full w-full -rotate-90"
                      viewBox="0 0 120 120"
                    >
                      <circle
                        cx="60"
                        cy="60"
                        r="52"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="8"
                        className="text-zinc-800"
                      />
                      <motion.circle
                        cx="60"
                        cy="60"
                        r="52"
                        fill="none"
                        stroke="url(#threatGradient)"
                        strokeWidth="8"
                        strokeLinecap="round"
                        strokeDasharray={2 * Math.PI * 52}
                        initial={{
                          strokeDashoffset: 2 * Math.PI * 52,
                        }}
                        animate={{
                          strokeDashoffset:
                            2 * Math.PI * 52 * (1 - threatScore / 100),
                        }}
                        transition={{ duration: 1, ease: "easeOut" }}
                      />
                      <defs>
                        <linearGradient
                          id="threatGradient"
                          x1="0%"
                          y1="0%"
                          x2="100%"
                          y2="0%"
                        >
                          <stop offset="0%" stopColor="#ef4444" />
                          <stop offset="100%" stopColor="#dc2626" />
                        </linearGradient>
                      </defs>
                    </svg>
                    <div className="text-center">
                      <motion.span
                        className="text-3xl font-bold text-red-400"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: 0.3 }}
                      >
                        {threatScore}
                      </motion.span>
                      <p className="text-[10px] uppercase tracking-wider text-zinc-500">
                        Threat
                      </p>
                    </div>
                  </div>

                  {/* DISARM tags */}
                  <div className="flex flex-wrap justify-center gap-2">
                    {disarmTags.map((tag) => (
                      <span
                        key={tag.id}
                        className="rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1 text-xs text-red-400"
                      >
                        {tag.id} &middot; {tag.label}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Engine Grid */}
                <EngineGrid animated />

                {/* Reset button */}
                <div className="flex justify-center">
                  <button
                    type="button"
                    onClick={handleReset}
                    className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-400 transition hover:border-zinc-500 hover:text-white"
                  >
                    <RotateCcw className="size-4" />
                    Try another example
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* CTA below demo */}
          <div className="mt-8 text-center">
            <p className="text-sm text-zinc-500">
              This is a preview. Sign up for full analysis with detailed reports.
            </p>
            <a
              href="/register"
              className="mt-4 inline-flex items-center justify-center rounded-lg bg-emerald-500 px-6 py-3 text-sm font-medium text-white transition-all hover:bg-emerald-600 hover:shadow-lg hover:shadow-emerald-500/20 hover:scale-[1.02] active:scale-[0.98]"
            >
              Get Started Free
            </a>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
