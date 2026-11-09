"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import {
  RotateCcw,
  Brain,
  BookOpen,
  FileText,
  AlertTriangle,
  CheckCircle,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";
import { scoreColor, scoreStroke } from "@/lib/colors";
import { ChapterHeading } from "@/components/landing/shared/ChapterHeading";

type ScanState = "idle" | "scanning" | "complete";

const exampleSources = [
  {
    exhibit: "A",
    url: "example-news.com/climate-article",
    label: "Mixed credibility",
    sublabel: "Climate news article",
  },
  {
    exhibit: "B",
    url: "blog.example.org/vaccine-study",
    label: "Low credibility",
    sublabel: "Anti-vaccine blog",
  },
  {
    exhibit: "C",
    url: "medium.com/ai-revolution-2025",
    label: "AI-generated",
    sublabel: "Medium post",
  },
] as const;

interface CheckResult {
  name: string;
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  status: "pass" | "warn" | "fail";
  label: string;
  detail: string;
}

const scanResults: Record<string, CheckResult[]> = {
  "example-news.com/climate-article": [
    { name: "Claim 1",      icon: CheckCircle,    status: "pass", label: "True",        detail: "CO2 levels match NOAA records" },
    { name: "Claim 2",      icon: AlertTriangle,  status: "fail", label: "False",       detail: "Temperature rise figure off by 40%" },
    { name: "AI signal",    icon: Brain,          status: "pass", label: "8% AI",       detail: "Mostly human-written" },
    { name: "Citation 1",   icon: BookOpen,       status: "pass", label: "Valid",       detail: "Nature 2024 — accessible" },
    { name: "Citation 2",   icon: BookOpen,       status: "warn", label: "Retracted",   detail: "Withdrawn Jan 2025" },
    { name: "Origin trace", icon: FileText,       status: "warn", label: "Traced",      detail: "False claim seeded on social" },
  ],
  "blog.example.org/vaccine-study": [
    { name: "Claim 1",      icon: AlertTriangle,  status: "fail", label: "False",       detail: "Cited study retracted in 2023" },
    { name: "Claim 2",      icon: AlertTriangle,  status: "fail", label: "Misleading",  detail: "Statistics out of context" },
    { name: "AI signal",    icon: Brain,          status: "warn", label: "72% AI",      detail: "High AI probability" },
    { name: "Citation 1",   icon: BookOpen,       status: "fail", label: "Retracted",   detail: "Wakefield 1998 — retracted 2010" },
    { name: "Citation 2",   icon: BookOpen,       status: "fail", label: "Inaccessible", detail: "Link returns 404" },
    { name: "Origin trace", icon: FileText,       status: "fail", label: "Disinfo",     detail: "Known disinfo network origin" },
  ],
  "medium.com/ai-revolution-2025": [
    { name: "Claim 1",       icon: CheckCircle,   status: "pass", label: "True",        detail: "GPT-4 benchmark verified" },
    { name: "Claim 2",       icon: CheckCircle,   status: "pass", label: "True",        detail: "Market size matches Statista" },
    { name: "AI signal",     icon: Brain,         status: "fail", label: "95% AI",      detail: "Almost entirely AI-generated" },
    { name: "Citation 1",    icon: BookOpen,      status: "pass", label: "Valid",       detail: "arXiv paper accessible" },
    { name: "Citation 2",    icon: BookOpen,      status: "pass", label: "Valid",       detail: "OpenAI blog verified" },
    { name: "Source quality", icon: FileText,     status: "warn", label: "Medium",      detail: "Non-peer-reviewed source" },
  ],
};

const scores: Record<string, number> = {
  "example-news.com/climate-article": 72,
  "blog.example.org/vaccine-study": 15,
  "medium.com/ai-revolution-2025": 58,
};

const statusStyles = {
  pass: "border-emerald-500/30 bg-emerald-500/5 text-emerald-700 dark:text-emerald-300",
  warn: "border-amber-500/30 bg-amber-500/5 text-amber-700 dark:text-amber-300",
  fail: "border-red-500/30 bg-red-500/5 text-red-700 dark:text-red-300",
} as const;

/** ───────────────────────────────────────────────────────────────────
 *  ScannerPreview — Section II, "How a finding reads"
 *
 *  Three pre-recorded exhibits laid out as case-file cards (Exhibit A
 *  / B / C) the user can open to inspect a real finding. The result
 *  view is the same as a live submission but with canned data.
 *  ─────────────────────────────────────────────────────────────────── */
export function ScannerPreview() {
  const [state, setState] = useState<ScanState>("idle");
  const [progress, setProgress] = useState(0);
  const [activeUrl, setActiveUrl] = useState<string>("");
  const reduce = useReducedMotion();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cleanup = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    intervalRef.current = null;
    timeoutRef.current = null;
  }, []);

  useEffect(() => cleanup, [cleanup]);

  const startScan = useCallback(
    (url: string) => {
      cleanup();
      setActiveUrl(url);
      setProgress(0);
      timeoutRef.current = setTimeout(() => {
        setState("scanning");
        const totalDuration = reduce ? 200 : 1800;
        const steps = 50;
        let i = 0;
        intervalRef.current = setInterval(() => {
          i++;
          setProgress((i / steps) * 100);
          if (i >= steps) {
            if (intervalRef.current) clearInterval(intervalRef.current);
            intervalRef.current = null;
            setState("complete");
          }
        }, totalDuration / steps);
      }, 200);
    },
    [cleanup, reduce],
  );

  const handleReset = useCallback(() => {
    cleanup();
    setState("idle");
    setActiveUrl("");
    setProgress(0);
  }, [cleanup]);

  const score = scores[activeUrl] ?? 0;
  const results = scanResults[activeUrl];
  const activeExhibit = exampleSources.find((e) => e.url === activeUrl)?.exhibit;

  return (
    <section id="how-it-works" className="py-28 sm:py-32">
      <div className="mx-auto max-w-5xl px-6">
        <ChapterHeading
          numeral="II"
          eyebrow="How a finding reads"
          title={
            <>
              Three exhibits.{" "}
              <span className="italic text-brand-fg">One scoring rubric.</span>
            </>
          }
          subtitle="Pick an exhibit to read the report a real submission would produce. The data is canned for these three; the format — claim verdicts, AI probability, citation status, credibility score — is what every reading carries."
        />

        <div className="mt-16">
          <AnimatePresence mode="wait">
            {state === "idle" && (
              <motion.div
                key="idle"
                initial={{ opacity: 0, y: reduce ? 0 : 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: reduce ? 0 : -8 }}
                transition={{ duration: reduce ? 0 : 0.3 }}
              >
                <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
                  {exampleSources.map((ex, i) => (
                    <motion.button
                      key={ex.url}
                      type="button"
                      onClick={() => startScan(ex.url)}
                      initial={{ opacity: 0, y: reduce ? 0 : 14 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ once: true, amount: 0.3 }}
                      transition={{
                        duration: reduce ? 0 : 0.5,
                        delay: reduce ? 0 : 0.05 + i * 0.08,
                        ease: [0.16, 1, 0.3, 1],
                      }}
                      className="group relative flex flex-col overflow-hidden rounded-sm border border-border-default bg-surface-card p-6 text-left transition-all hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-[0_18px_40px_-20px_color-mix(in_oklab,var(--brand)_40%,transparent)] active:translate-y-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
                    >
                      {/* Top hairline */}
                      <span
                        aria-hidden="true"
                        className="pointer-events-none absolute left-4 right-4 top-0 h-px bg-border-strong"
                      />

                      {/* Exhibit label */}
                      <div className="flex items-baseline justify-between">
                        <span className="font-display text-xs font-semibold tracking-[0.16em] text-brand-fg">
                          EXHIBIT {ex.exhibit}
                        </span>
                        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-fg-tertiary">
                          № {String(i + 1).padStart(2, "0")}
                        </span>
                      </div>

                      {/* Verdict-style title */}
                      <p className="mt-5 font-display text-xl font-semibold leading-tight text-fg-primary">
                        {ex.label}
                      </p>

                      <p className="editorial-italic mt-1 text-sm text-fg-secondary">
                        {ex.sublabel}
                      </p>

                      <hr className="rule-hair my-5" />

                      <p className="truncate font-mono text-xs text-fg-primary">
                        {ex.url}
                      </p>

                      <p className="mt-4 inline-flex items-center gap-1.5 text-xs font-medium text-brand-fg transition-transform group-hover:translate-x-0.5">
                        Open exhibit
                        <ArrowRight className="h-3 w-3" strokeWidth={2} />
                      </p>
                    </motion.button>
                  ))}
                </div>
              </motion.div>
            )}

            {state === "scanning" && (
              <motion.div
                key="scanning"
                initial={{ opacity: 0, y: reduce ? 0 : 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: reduce ? 0 : -8 }}
                transition={{ duration: reduce ? 0 : 0.3 }}
                className="space-y-5"
                aria-live="polite"
              >
                <div className="rounded-sm border border-border-default bg-surface-card p-5">
                  <div className="flex items-baseline justify-between">
                    <span className="label-eyebrow text-fg-tertiary">
                      Reading exhibit {activeExhibit}
                    </span>
                    <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-fg-tertiary">
                      Live
                    </span>
                  </div>
                  <p className="mt-2 truncate font-mono text-sm text-fg-primary">
                    {activeUrl}
                  </p>
                </div>

                <div
                  role="progressbar"
                  aria-valuenow={Math.round(progress)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  className="h-1 w-full overflow-hidden rounded-full bg-border-subtle"
                >
                  <motion.div
                    className="h-full rounded-full bg-brand"
                    style={{ width: `${progress}%` }}
                    transition={{ duration: 0.05 }}
                  />
                </div>

                <p className="editorial-italic text-center text-sm text-fg-tertiary">
                  Extracting claims · checking facts · detecting AI signal …
                </p>
              </motion.div>
            )}

            {state === "complete" && results && (
              <motion.div
                key="complete"
                initial={{ opacity: 0, y: reduce ? 0 : 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: reduce ? 0 : -8 }}
                transition={{ duration: reduce ? 0 : 0.3 }}
                className="space-y-10"
              >
                {/* Verdict header — case file masthead */}
                <div className="relative overflow-hidden rounded-sm border border-border-default bg-surface-card p-7">
                  <span
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-x-5 top-0 h-px bg-border-strong"
                  />

                  <div className="flex flex-col items-center gap-7 sm:flex-row sm:gap-10">
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
                          strokeWidth="6"
                          className="text-border-subtle"
                        />
                        <motion.circle
                          cx="60"
                          cy="60"
                          r="52"
                          fill="none"
                          stroke={scoreStroke(score)}
                          strokeWidth="6"
                          strokeLinecap="round"
                          strokeDasharray={2 * Math.PI * 52}
                          initial={{ strokeDashoffset: 2 * Math.PI * 52 }}
                          animate={{
                            strokeDashoffset:
                              2 * Math.PI * 52 * (1 - score / 100),
                          }}
                          transition={{ duration: reduce ? 0 : 0.9, ease: "easeOut" }}
                        />
                      </svg>
                      <div className="text-center">
                        <span
                          className={cn(
                            "font-display text-3xl font-semibold tabular-nums",
                            scoreColor(score),
                          )}
                        >
                          {score}
                        </span>
                        <p className="label-eyebrow mt-0.5 text-fg-tertiary">
                          Cred.
                        </p>
                      </div>
                    </div>

                    <div className="min-w-0 flex-1 text-center sm:text-left">
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="label-eyebrow text-brand-fg">
                          Exhibit {activeExhibit}
                        </span>
                        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-fg-tertiary">
                          Reading complete
                        </span>
                      </div>
                      <p className="mt-2 truncate font-mono text-sm text-fg-primary">
                        {activeUrl}
                      </p>
                      <p className="editorial-italic mt-3 text-sm text-fg-secondary">
                        Six findings recorded. The credibility number is
                        the sum of these deductions.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Findings list — six labeled cards in a 3-col grid */}
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {results.map((check, index) => {
                    const Icon = check.icon;
                    return (
                      <motion.div
                        key={check.name}
                        initial={{ opacity: 0, y: reduce ? 0 : 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{
                          duration: reduce ? 0 : 0.3,
                          delay: reduce ? 0 : index * 0.06,
                        }}
                        className="rounded-sm border border-border-default bg-surface-card p-4"
                      >
                        <div className="flex items-center gap-2">
                          <Icon
                            className="h-4 w-4 text-fg-tertiary"
                            strokeWidth={1.5}
                          />
                          <span className="text-sm font-medium text-fg-primary">
                            {check.name}
                          </span>
                          <span
                            className={cn(
                              "ml-auto inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[10px] tracking-wider uppercase",
                              statusStyles[check.status],
                            )}
                          >
                            {check.label}
                          </span>
                        </div>
                        <p className="editorial-italic mt-2 text-sm leading-snug text-fg-secondary">
                          {check.detail}
                        </p>
                      </motion.div>
                    );
                  })}
                </div>

                <div className="flex flex-col items-center gap-4 border-t border-border-subtle pt-6 sm:flex-row sm:justify-center sm:gap-8">
                  <button
                    type="button"
                    onClick={handleReset}
                    className="inline-flex items-center gap-2 rounded-sm border border-border-default px-4 py-2 text-sm text-fg-primary transition-all hover:bg-surface-card active:translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
                  >
                    <RotateCcw className="h-4 w-4" strokeWidth={1.75} />
                    Open another exhibit
                  </button>
                  <Link
                    href="/register"
                    className="group inline-flex items-center gap-1.5 text-sm font-medium text-brand-fg transition-colors hover:text-brand-hover focus-visible:outline-none"
                  >
                    <span className="ink-underline">
                      Run a reading on your own source
                    </span>
                    <ArrowRight
                      className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5"
                      strokeWidth={2}
                    />
                  </Link>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}
