"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  RotateCcw,
  Shield,
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
import { ScrollReveal } from "@/components/landing/shared/ScrollReveal";

type ScanState = "idle" | "scanning" | "complete";

/**
 * Pre-recorded example outputs. The demo is intentionally locked to these
 * three URLs — the input is read-only and only the example chips trigger
 * a scan. We used to allow free paste, then fall back to canned data for
 * any URL we didn't recognize, which let users post their own URL and see
 * fake results. A research-integrity tool faking its own demo is the
 * worst-possible brand contradiction; the lockdown removes it.
 */
const exampleSources = [
  {
    url: "example-news.com/climate-article",
    label: "Mixed credibility (climate news)",
  },
  {
    url: "blog.example.org/vaccine-study",
    label: "Low credibility (anti-vax blog)",
  },
  {
    url: "medium.com/ai-revolution-2025",
    label: "AI-generated (Medium post)",
  },
] as const;

interface CheckResult {
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  status: "pass" | "warn" | "fail";
  label: string;
  detail: string;
}

const scanResults: Record<string, CheckResult[]> = {
  "example-news.com/climate-article": [
    { name: "Claim 1", icon: CheckCircle, status: "pass", label: "True", detail: "CO2 levels match NOAA records" },
    { name: "Claim 2", icon: AlertTriangle, status: "fail", label: "False", detail: "Temperature rise figure off by 40%" },
    { name: "AI detection", icon: Brain, status: "pass", label: "8% AI", detail: "Mostly human-written" },
    { name: "Citation 1", icon: BookOpen, status: "pass", label: "Valid", detail: "Nature 2024 — accessible" },
    { name: "Citation 2", icon: BookOpen, status: "warn", label: "Retracted", detail: "Withdrawn Jan 2025" },
    { name: "Origin trace", icon: FileText, status: "warn", label: "Traced", detail: "False claim seeded on social" },
  ],
  "blog.example.org/vaccine-study": [
    { name: "Claim 1", icon: AlertTriangle, status: "fail", label: "False", detail: "Cited study retracted in 2023" },
    { name: "Claim 2", icon: AlertTriangle, status: "fail", label: "Misleading", detail: "Statistics out of context" },
    { name: "AI detection", icon: Brain, status: "warn", label: "72% AI", detail: "High AI probability" },
    { name: "Citation 1", icon: BookOpen, status: "fail", label: "Retracted", detail: "Wakefield 1998 — retracted 2010" },
    { name: "Citation 2", icon: BookOpen, status: "fail", label: "Inaccessible", detail: "Link returns 404" },
    { name: "Origin trace", icon: FileText, status: "fail", label: "Disinfo", detail: "Known disinfo network origin" },
  ],
  "medium.com/ai-revolution-2025": [
    { name: "Claim 1", icon: CheckCircle, status: "pass", label: "True", detail: "GPT-4 benchmark verified" },
    { name: "Claim 2", icon: CheckCircle, status: "pass", label: "True", detail: "Market size matches Statista" },
    { name: "AI detection", icon: Brain, status: "fail", label: "95% AI", detail: "Almost entirely AI-generated" },
    { name: "Citation 1", icon: BookOpen, status: "pass", label: "Valid", detail: "arXiv paper accessible" },
    { name: "Citation 2", icon: BookOpen, status: "pass", label: "Valid", detail: "OpenAI blog verified" },
    { name: "Source quality", icon: Shield, status: "warn", label: "Medium", detail: "Non-peer-reviewed source" },
  ],
};

const scores: Record<string, number> = {
  "example-news.com/climate-article": 72,
  "blog.example.org/vaccine-study": 15,
  "medium.com/ai-revolution-2025": 58,
};

const statusStyles = {
  pass: "border-emerald-500/30 bg-emerald-500/5 text-emerald-300",
  warn: "border-amber-500/30 bg-amber-500/5 text-amber-300",
  fail: "border-red-500/30 bg-red-500/5 text-red-300",
} as const;

export function ScannerPreview() {
  const [state, setState] = useState<ScanState>("idle");
  const [progress, setProgress] = useState(0);
  const [activeUrl, setActiveUrl] = useState<string>("");
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

  useEffect(() => cleanup, [cleanup]);

  const startScan = useCallback(
    (url: string) => {
      cleanup();
      setActiveUrl(url);
      setProgress(0);

      timeoutRef.current = setTimeout(() => {
        setState("scanning");
        const totalDuration = 2200;
        const steps = 50;
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
        }, totalDuration / steps);
      }, 250);
    },
    [cleanup],
  );

  const handleReset = useCallback(() => {
    cleanup();
    setState("idle");
    setActiveUrl("");
    setProgress(0);
  }, [cleanup]);

  const score = scores[activeUrl] ?? 0;
  const results = scanResults[activeUrl];

  return (
    <section id="how-it-works" className="py-24">
      <div className="mx-auto max-w-4xl px-6">
        <div className="mb-10 max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">
            How it works
          </p>
          <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-balance text-white sm:text-4xl">
            Three pre-recorded examples. Real scoring rubric.
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-zinc-400">
            Pick a sample URL below to see the kind of report a real
            submission produces. The output you see is canned for the
            examples; the rubric (claim verdicts, AI probability,
            citation status, credibility score) is what you'll get on
            real content after registering.
          </p>
        </div>

        <ScrollReveal>
          <AnimatePresence mode="wait">
            {state === "idle" && (
              <motion.div
                key="idle"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
              >
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  {exampleSources.map((ex) => (
                    <button
                      key={ex.url}
                      type="button"
                      onClick={() => startScan(ex.url)}
                      className="group rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 text-left transition-all hover:border-emerald-500/40 hover:bg-zinc-900/60 active:translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50"
                    >
                      <p className="text-xs uppercase tracking-wider text-zinc-500">
                        {ex.label}
                      </p>
                      <p className="mt-2 truncate font-mono text-sm text-zinc-200">
                        {ex.url}
                      </p>
                      <p className="mt-3 inline-flex items-center gap-1 text-xs text-emerald-400 transition-transform group-hover:translate-x-0.5">
                        Run example
                        <ArrowRight className="h-3 w-3" />
                      </p>
                    </button>
                  ))}
                </div>
              </motion.div>
            )}

            {state === "scanning" && (
              <motion.div
                key="scanning"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
                className="space-y-5"
                aria-live="polite"
              >
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
                  <p className="text-xs uppercase tracking-wider text-zinc-500">
                    Verifying
                  </p>
                  <p className="mt-1 truncate font-mono text-sm text-zinc-200">
                    {activeUrl}
                  </p>
                </div>
                <div
                  role="progressbar"
                  aria-valuenow={Math.round(progress)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800"
                >
                  <motion.div
                    className="h-full rounded-full bg-emerald-500"
                    style={{ width: `${progress}%` }}
                    transition={{ duration: 0.05 }}
                  />
                </div>
                <p className="text-center text-sm text-zinc-500">
                  Extracting claims, checking facts, detecting AI content...
                </p>
              </motion.div>
            )}

            {state === "complete" && results && (
              <motion.div
                key="complete"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
                className="space-y-8"
              >
                <div className="flex flex-col items-center gap-6 rounded-xl border border-zinc-800 bg-zinc-900/40 p-6 sm:flex-row sm:gap-8">
                  <div className="relative flex h-24 w-24 shrink-0 items-center justify-center">
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
                        stroke={scoreStroke(score)}
                        strokeWidth="8"
                        strokeLinecap="round"
                        strokeDasharray={2 * Math.PI * 52}
                        initial={{ strokeDashoffset: 2 * Math.PI * 52 }}
                        animate={{
                          strokeDashoffset:
                            2 * Math.PI * 52 * (1 - score / 100),
                        }}
                        transition={{ duration: 0.9, ease: "easeOut" }}
                      />
                    </svg>
                    <div className="text-center">
                      <span
                        className={cn("font-display text-3xl font-bold tabular-nums", scoreColor(score))}
                      >
                        {score}
                      </span>
                      <p className="text-[10px] uppercase tracking-wider text-zinc-500">
                        Credibility
                      </p>
                    </div>
                  </div>
                  <div className="min-w-0 flex-1 text-center sm:text-left">
                    <p className="text-xs uppercase tracking-wider text-zinc-500">
                      Verified
                    </p>
                    <p className="mt-1 truncate font-mono text-sm text-zinc-200">
                      {activeUrl}
                    </p>
                    <p className="mt-2 text-xs text-zinc-500">
                      Example output — your real submissions get the full
                      report with sources and remediation.
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {results.map((check, index) => {
                    const Icon = check.icon;
                    return (
                      <motion.div
                        key={check.name}
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, delay: index * 0.06 }}
                        className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4"
                      >
                        <div className="flex items-center gap-2">
                          <Icon className="h-4 w-4 text-zinc-500" aria-hidden="true" />
                          <span className="text-sm font-medium text-white">
                            {check.name}
                          </span>
                          <span
                            className={cn(
                              "ml-auto inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider",
                              statusStyles[check.status],
                            )}
                          >
                            {check.label}
                          </span>
                        </div>
                        <p className="mt-2 text-xs leading-relaxed text-zinc-500">
                          {check.detail}
                        </p>
                      </motion.div>
                    );
                  })}
                </div>

                <div className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center sm:gap-4">
                  <button
                    type="button"
                    onClick={handleReset}
                    className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 transition-all hover:border-zinc-500 hover:bg-zinc-800 active:translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50"
                  >
                    <RotateCcw className="h-4 w-4" />
                    Try another example
                  </button>
                  <Link
                    href="/register"
                    className="inline-flex items-center gap-2 text-sm text-emerald-400 transition-colors hover:text-emerald-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 focus-visible:rounded-md"
                  >
                    Run on your own source
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </ScrollReveal>
      </div>
    </section>
  );
}
