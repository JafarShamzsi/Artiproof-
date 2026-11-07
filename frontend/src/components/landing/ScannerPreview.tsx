"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, RotateCcw, Shield, Brain, BookOpen, FileText, AlertTriangle, CheckCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { SectionHeading } from "@/components/landing/shared/SectionHeading";
import { ScrollReveal } from "@/components/landing/shared/ScrollReveal";
import { GlowCard } from "@/components/landing/shared/GlowCard";

type ScanState = "idle" | "scanning" | "complete";

const exampleSources = [
  "https://example-news.com/climate-article",
  "https://blog.example.org/vaccine-study",
  "https://medium.com/ai-revolution-2025",
] as const;

interface CheckResult {
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  status: "pass" | "warn" | "fail";
  label: string;
  detail: string;
}

const scanResults: Record<string, CheckResult[]> = {
  "https://example-news.com/climate-article": [
    { name: "Claim #1", icon: CheckCircle, status: "pass", label: "TRUE", detail: "CO2 levels data matches NOAA records" },
    { name: "Claim #2", icon: AlertTriangle, status: "fail", label: "FALSE", detail: "Temperature rise figure exaggerated by 40%" },
    { name: "AI Detection", icon: Brain, status: "pass", label: "8% AI", detail: "Article appears mostly human-written" },
    { name: "Citation #1", icon: BookOpen, status: "pass", label: "VALID", detail: "Nature 2024 paper accessible and current" },
    { name: "Citation #2", icon: BookOpen, status: "warn", label: "RETRACTED", detail: "This source was retracted in Jan 2025" },
    { name: "Origin Trace", icon: FileText, status: "warn", label: "TRACED", detail: "False claim originated on social media" },
  ],
  "https://blog.example.org/vaccine-study": [
    { name: "Claim #1", icon: AlertTriangle, status: "fail", label: "FALSE", detail: "Study cited was retracted in 2023" },
    { name: "Claim #2", icon: AlertTriangle, status: "fail", label: "MISLEADING", detail: "Statistics taken out of context" },
    { name: "AI Detection", icon: Brain, status: "warn", label: "72% AI", detail: "High probability of AI-generated content" },
    { name: "Citation #1", icon: BookOpen, status: "fail", label: "RETRACTED", detail: "Wakefield study — retracted 2010" },
    { name: "Citation #2", icon: BookOpen, status: "fail", label: "INACCESSIBLE", detail: "Link returns 404 error" },
    { name: "Origin Trace", icon: FileText, status: "fail", label: "DISINFO", detail: "Claims trace to known disinfo network" },
  ],
  "https://medium.com/ai-revolution-2025": [
    { name: "Claim #1", icon: CheckCircle, status: "pass", label: "TRUE", detail: "GPT-4 benchmark data verified" },
    { name: "Claim #2", icon: CheckCircle, status: "pass", label: "TRUE", detail: "Market size figure matches Statista" },
    { name: "AI Detection", icon: Brain, status: "fail", label: "95% AI", detail: "Almost entirely AI-generated content" },
    { name: "Citation #1", icon: BookOpen, status: "pass", label: "VALID", detail: "arXiv paper accessible and current" },
    { name: "Citation #2", icon: BookOpen, status: "pass", label: "VALID", detail: "OpenAI blog post verified" },
    { name: "Source Quality", icon: Shield, status: "warn", label: "MEDIUM", detail: "Medium blog — non-peer-reviewed source" },
  ],
};

const scores: Record<string, number> = {
  "https://example-news.com/climate-article": 72,
  "https://blog.example.org/vaccine-study": 15,
  "https://medium.com/ai-revolution-2025": 58,
};

const statusStyles = {
  pass: { dot: "bg-emerald-400", badge: "bg-emerald-500/20 text-emerald-400" },
  warn: { dot: "bg-yellow-400", badge: "bg-yellow-500/20 text-yellow-400" },
  fail: { dot: "bg-red-400", badge: "bg-red-500/20 text-red-400" },
};

const scoreColor = (s: number) =>
  s >= 70 ? "text-emerald-400" : s >= 40 ? "text-yellow-400" : "text-red-400";

const scoreStroke = (s: number) =>
  s >= 70 ? "#10b981" : s >= 40 ? "#eab308" : "#ef4444";

export function ScannerPreview() {
  const [input, setInput] = useState("");
  const [state, setState] = useState<ScanState>("idle");
  const [progress, setProgress] = useState(0);
  const [activeUrl, setActiveUrl] = useState("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cleanup = useCallback(() => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
  }, []);

  useEffect(() => { return cleanup; }, [cleanup]);

  const startScan = useCallback(
    (url: string) => {
      cleanup();
      setActiveUrl(url);
      setInput(url);
      setProgress(0);

      timeoutRef.current = setTimeout(() => {
        setState("scanning");
        const totalDuration = 2500;
        const steps = 50;
        let currentStep = 0;

        intervalRef.current = setInterval(() => {
          currentStep++;
          setProgress((currentStep / steps) * 100);
          if (currentStep >= steps) {
            if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
            setState("complete");
          }
        }, totalDuration / steps);
      }, 300);
    },
    [cleanup]
  );

  const handleReset = useCallback(() => {
    cleanup();
    setState("idle");
    setInput("");
    setActiveUrl("");
    setProgress(0);
  }, [cleanup]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (input.trim() && state === "idle") startScan(input.trim());
    },
    [input, state, startScan]
  );

  const score = scores[activeUrl] ?? 55;
  const results = scanResults[activeUrl] ?? scanResults["https://example-news.com/climate-article"];

  return (
    <section id="scanner" className="py-24">
      <div className="mx-auto max-w-4xl px-6">
        <SectionHeading eyebrow="LIVE DEMO" title="See It In Action" gradient="Action" />

        <ScrollReveal>
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
                    <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-zinc-500" />
                    <input
                      type="text"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      placeholder="Paste an article URL to verify..."
                      className="w-full rounded-xl border border-zinc-700/50 bg-zinc-900 p-4 pl-12 pr-14 text-white placeholder-zinc-500 outline-none transition-colors focus:border-emerald-500/50"
                    />
                    <button
                      type="submit"
                      className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg bg-emerald-500 p-2 text-white transition-all hover:bg-emerald-600 hover:shadow-lg hover:shadow-emerald-500/20"
                    >
                      <Search className="size-4" />
                    </button>
                  </div>
                </form>
                <div className="mt-4 flex flex-wrap gap-2">
                  {exampleSources.map((url) => (
                    <button
                      key={url}
                      type="button"
                      onClick={() => startScan(url)}
                      className="cursor-pointer rounded-full border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400 transition hover:border-emerald-500/50 hover:text-emerald-400"
                    >
                      {url}
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
                <div className="rounded-xl border border-zinc-700/50 bg-zinc-900 p-4">
                  <p className="text-sm text-zinc-400">Verifying:</p>
                  <p className="mt-1 font-medium text-white">{activeUrl}</p>
                </div>
                <div className="space-y-3">
                  <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-800">
                    <motion.div
                      className="h-full rounded-full bg-emerald-500"
                      style={{ width: `${progress}%` }}
                      transition={{ duration: 0.05 }}
                    />
                  </div>
                  <p className="text-center text-sm text-zinc-400">
                    Extracting claims, checking facts, detecting AI content...
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
                <div className="rounded-xl border border-zinc-700/50 bg-zinc-900 p-4">
                  <p className="text-sm text-zinc-400">Verification complete:</p>
                  <p className="mt-1 font-medium text-white">{activeUrl}</p>
                </div>

                <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center sm:gap-8">
                  <div className="relative flex h-28 w-28 shrink-0 items-center justify-center">
                    <svg className="absolute inset-0 h-full w-full -rotate-90" viewBox="0 0 120 120">
                      <circle cx="60" cy="60" r="52" fill="none" stroke="currentColor" strokeWidth="8" className="text-zinc-800" />
                      <motion.circle
                        cx="60" cy="60" r="52" fill="none"
                        stroke={scoreStroke(score)}
                        strokeWidth="8" strokeLinecap="round"
                        strokeDasharray={2 * Math.PI * 52}
                        initial={{ strokeDashoffset: 2 * Math.PI * 52 }}
                        animate={{ strokeDashoffset: 2 * Math.PI * 52 * (1 - score / 100) }}
                        transition={{ duration: 1, ease: "easeOut" }}
                      />
                    </svg>
                    <div className="text-center">
                      <motion.span
                        className={cn("text-3xl font-bold", scoreColor(score))}
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}
                      >
                        {score}
                      </motion.span>
                      <p className="text-xs text-zinc-500">Credibility</p>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {results.map((check, index) => {
                    const style = statusStyles[check.status];
                    const Icon = check.icon;
                    return (
                      <motion.div
                        key={check.name}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.4, delay: index * 0.1 }}
                      >
                        <GlowCard className="p-4" glowColor="emerald">
                          <div className="flex items-center gap-2">
                            <span className="relative flex h-2 w-2">
                              <span className={cn("absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping", style.dot)} />
                              <span className={cn("relative inline-flex h-2 w-2 rounded-full", style.dot)} />
                            </span>
                            <Icon className="h-4 w-4 text-zinc-400" />
                            <span className="text-sm font-medium text-white">{check.name}</span>
                          </div>
                          <div className="mt-2">
                            <span className={cn("inline-block rounded-full px-2 py-0.5 text-xs uppercase", style.badge)}>
                              {check.label}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-zinc-500">{check.detail}</p>
                        </GlowCard>
                      </motion.div>
                    );
                  })}
                </div>

                <div className="flex justify-center">
                  <button
                    type="button"
                    onClick={handleReset}
                    className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-400 transition hover:border-zinc-500 hover:text-white"
                  >
                    <RotateCcw className="size-4" />
                    Try another source
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="mt-8 text-center">
            <p className="text-sm text-zinc-500">
              This is a preview. Register for full source verification with detailed reports.
            </p>
            <a
              href="/register"
              className="mt-4 inline-flex items-center justify-center rounded-lg bg-emerald-500 px-6 py-3 text-sm font-medium text-white transition-all hover:bg-emerald-600 hover:shadow-lg hover:shadow-emerald-500/20 hover:scale-[1.02] active:scale-[0.98]"
            >
              Start Checking Sources
            </a>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
