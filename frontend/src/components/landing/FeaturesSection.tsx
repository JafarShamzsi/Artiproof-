"use client";

import { useRef } from "react";
import { motion, useInView } from "framer-motion";
import {
  Shield,
  Brain,
  BookOpen,
  Users,
  GitBranch,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { ScrollReveal } from "@/components/landing/shared/ScrollReveal";

// ─── Mini-visualizations (one per engine) ─────────────────────────────

function CredibilityGauge() {
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });
  const score = 85;
  const radius = 48;
  const circumference = Math.PI * radius;
  const progress = (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg
        ref={ref}
        width="180"
        height="100"
        viewBox="0 0 140 90"
        className="overflow-visible"
        aria-hidden="true"
      >
        <path
          d="M 10 70 A 60 60 0 0 1 130 70"
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          strokeLinecap="round"
          className="text-border-subtle"
        />
        <motion.path
          d="M 10 70 A 60 60 0 0 1 130 70"
          fill="none"
          stroke="#10b981"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={inView ? { strokeDashoffset: circumference - progress } : {}}
          transition={{ duration: 1.0, ease: [0.16, 1, 0.3, 1], delay: 0.2 }}
        />
      </svg>
      <span className="-mt-7 font-display text-4xl font-semibold tabular-nums text-emerald-500 dark:text-emerald-400">
        {score}
      </span>
      <span className="mt-1 text-[10px] uppercase tracking-wider text-fg-tertiary">
        Credibility score
      </span>
    </div>
  );
}

function ClaimVerdicts() {
  const verdicts = [
    { label: "Climate data accurate", v: "True", c: "text-emerald-700 dark:text-emerald-300", bar: "bg-emerald-500" },
    { label: "Vaccine claim disputed", v: "False", c: "text-red-700 dark:text-red-300", bar: "bg-red-500" },
    { label: "Source outdated (2017)", v: "Misleading", c: "text-amber-700 dark:text-amber-300", bar: "bg-amber-500" },
  ];
  return (
    <div className="space-y-2.5">
      {verdicts.map((v) => (
        <div
          key={v.label}
          className="flex items-center gap-3 rounded-md border border-border-default bg-surface-base px-3 py-2.5"
        >
          <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", v.bar)} />
          <span className="flex-1 truncate text-xs text-fg-primary">{v.label}</span>
          <span className={cn("text-[10px] uppercase tracking-wider", v.c)}>
            {v.v}
          </span>
        </div>
      ))}
    </div>
  );
}

function AIDetectionBars() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });
  const paragraphs = [
    { label: "P1", prob: 0.12 },
    { label: "P2", prob: 0.89 },
    { label: "P3", prob: 0.05 },
    { label: "P4", prob: 0.95 },
    { label: "P5", prob: 0.08 },
    { label: "P6", prob: 0.21 },
  ];
  return (
    <div ref={ref} className="space-y-2 font-mono">
      {paragraphs.map((p, i) => (
        <div key={p.label} className="flex items-center gap-2">
          <span className="w-6 text-[10px] text-fg-tertiary">{p.label}</span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-border-subtle">
            <motion.div
              className={cn(
                "h-full rounded-full",
                p.prob > 0.7 ? "bg-red-500" : "bg-emerald-500",
              )}
              initial={{ width: 0 }}
              animate={inView ? { width: `${p.prob * 100}%` } : {}}
              transition={{
                delay: 0.1 + i * 0.06,
                duration: 0.6,
                ease: [0.16, 1, 0.3, 1],
              }}
            />
          </div>
          <span className="w-9 text-right text-[10px] tabular-nums text-fg-tertiary">
            {Math.round(p.prob * 100)}%
          </span>
        </div>
      ))}
    </div>
  );
}

function CitationNetwork() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });

  return (
    <div ref={ref} className="rounded-xl border border-border-default bg-surface-base p-4">
      <svg viewBox="0 0 280 140" className="h-full w-full" aria-hidden="true">
        {[
          { x1: 140, y1: 70, x2: 60, y2: 36, suspicious: false },
          { x1: 140, y1: 70, x2: 60, y2: 104, suspicious: false },
          { x1: 140, y1: 70, x2: 220, y2: 36, suspicious: false },
          { x1: 140, y1: 70, x2: 220, y2: 104, suspicious: false },
          { x1: 60, y1: 36, x2: 60, y2: 104, suspicious: false },
          { x1: 60, y1: 36, x2: 220, y2: 36, suspicious: true },
          { x1: 60, y1: 104, x2: 220, y2: 104, suspicious: true },
          { x1: 220, y1: 36, x2: 220, y2: 104, suspicious: true },
        ].map((line, i) => (
          <motion.line
            key={i}
            x1={line.x1}
            y1={line.y1}
            x2={line.x2}
            y2={line.y2}
            stroke={line.suspicious ? "#ef4444" : "currentColor"}
            strokeWidth={line.suspicious ? 1.5 : 1}
            className={line.suspicious ? "" : "text-border-strong"}
            initial={{ pathLength: 0, opacity: 0 }}
            animate={inView ? { pathLength: 1, opacity: line.suspicious ? 0.7 : 0.5 } : {}}
            transition={{ delay: 0.2 + i * 0.05, duration: 0.6 }}
          />
        ))}
        {[
          { cx: 140, cy: 70, r: 7, color: "var(--brand)" },
          { cx: 60, cy: 36, r: 5, color: "currentColor", className: "text-fg-tertiary" },
          { cx: 60, cy: 104, r: 5, color: "currentColor", className: "text-fg-tertiary" },
          { cx: 220, cy: 36, r: 5, color: "#ef4444" },
          { cx: 220, cy: 104, r: 5, color: "#ef4444" },
        ].map((node, i) => (
          <motion.circle
            key={i}
            cx={node.cx}
            cy={node.cy}
            r={node.r}
            fill={node.color}
            className={node.className}
            initial={{ scale: 0 }}
            animate={inView ? { scale: 1 } : {}}
            transition={{
              delay: 0.6 + i * 0.05,
              duration: 0.4,
              ease: [0.16, 1, 0.3, 1],
            }}
            style={{ transformOrigin: `${node.cx}px ${node.cy}px` }}
          />
        ))}
      </svg>
    </div>
  );
}

function IntegrityDelta() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });

  return (
    <div
      ref={ref}
      className="space-y-4 rounded-xl border border-border-default bg-surface-base p-5 font-mono"
    >
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-fg-tertiary">Reported h-index</span>
        <motion.span
          className="text-xl font-bold tabular-nums text-fg-secondary line-through decoration-border-strong"
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ delay: 0.2, duration: 0.4 }}
        >
          42
        </motion.span>
      </div>
      <div className="border-t border-border-subtle" />
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-brand-fg">Adjusted</span>
        <motion.span
          className="font-display text-3xl font-semibold tabular-nums text-brand-fg"
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ delay: 0.5, duration: 0.4 }}
        >
          27
        </motion.span>
      </div>
      <p className="text-[10px] leading-relaxed text-fg-tertiary">
        After removing 312 self-citations and 84 ring citations across 18 papers.
      </p>
    </div>
  );
}

// ─── Engine spec ────────────────────────────────────────────────────────

interface Engine {
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  description: string;
  metric: string;
  visual: React.ReactNode;
}

const engines: Engine[] = [
  {
    icon: Shield,
    eyebrow: "Source verification",
    title: "Every claim gets a verdict and a source.",
    description:
      "Each factual claim is extracted, fact-checked, and scored against external databases. The credibility number is a sum of recorded deductions, not a black box.",
    metric: "Verifies claims against the Google Fact Check API",
    visual: <CredibilityGauge />,
  },
  {
    icon: BookOpen,
    eyebrow: "Claim analysis",
    title: "Read the verdicts, not a percentage.",
    description:
      "True, false, misleading, partially true, or unverified. Each verdict ships with the source that backs it. No bulk score, just specific calls you can defend in writing.",
    metric: "Up to 15 claims per submission",
    visual: <ClaimVerdicts />,
  },
  {
    icon: Brain,
    eyebrow: "AI content detection",
    title: "Per-paragraph probability, not a single number.",
    description:
      "A document is rarely all-AI or all-human. We score each paragraph separately so you can see exactly where the boundary lives, with a confidence level on each call.",
    metric: "Analyzes up to 20 paragraphs per document",
    visual: <AIDetectionBars />,
  },
  {
    icon: GitBranch,
    eyebrow: "Citation rings",
    title: "Detect mutual-citation networks.",
    description:
      "Groups of researchers who inflate each other's citation counts through circular references. We surface the network and which authors anchor it.",
    metric: "Detects rings of 5+ papers with mutual citations",
    visual: <CitationNetwork />,
  },
  {
    icon: Users,
    eyebrow: "Researcher integrity",
    title: "An h-index that excludes self-citations.",
    description:
      "h-index and total citation counts recomputed after removing self-citations and ring citations. The number you'd defend on a tenure committee.",
    metric: "Adjusts h-index for self-citation inflation",
    visual: <IntegrityDelta />,
  },
];

// ─── Section ────────────────────────────────────────────────────────────

export function FeaturesSection() {
  return (
    <section id="features" className="py-24 sm:py-28">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-20 max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-fg-tertiary">
            Five engines
          </p>
          <h2 className="mt-3 font-display text-4xl font-semibold leading-[1.05] tracking-tight text-balance text-fg-primary sm:text-5xl">
            Each engine returns{" "}
            <span className="italic text-brand-fg">evidence,</span> not a
            verdict.
          </h2>
        </div>

        <div className="space-y-24 md:space-y-32">
          {engines.map((engine, i) => (
            <EngineRow key={engine.eyebrow} engine={engine} flip={i % 2 === 1} />
          ))}
        </div>

        {/* Regional commitment — typographic statement, not a card. */}
        <ScrollReveal delay={0.1} className="mt-32">
          <div className="border-t border-border-subtle pt-12">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-brand-fg">
              Built for the EaP region
            </p>
            <p className="mt-3 max-w-3xl font-display text-2xl font-medium leading-snug text-balance text-fg-primary sm:text-3xl">
              Native Azerbaijani and Russian. Local compliance. Pricing that
              works for a regional university budget, not a US R1.
            </p>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}

function EngineRow({ engine, flip }: { engine: Engine; flip: boolean }) {
  const Icon = engine.icon;
  return (
    <ScrollReveal>
      <div
        className={cn(
          "grid grid-cols-1 items-center gap-10 lg:grid-cols-2 lg:gap-16",
          flip && "lg:[&>:first-child]:order-2",
        )}
      >
        <div>
          <div className="flex items-center gap-2">
            <Icon
              className="h-4 w-4 text-brand-fg"
              strokeWidth={1.5}
              aria-hidden="true"
            />
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-brand-fg">
              {engine.eyebrow}
            </p>
          </div>
          <h3 className="mt-3 font-display text-3xl font-semibold leading-[1.1] tracking-tight text-balance text-fg-primary sm:text-4xl">
            {engine.title}
          </h3>
          <p className="mt-5 max-w-md text-base leading-relaxed text-fg-secondary">
            {engine.description}
          </p>
          <p className="mt-6 inline-flex items-center gap-2 rounded-full border border-border-default bg-surface-card px-3 py-1.5 text-xs text-fg-primary">
            <span className="h-1.5 w-1.5 rounded-full bg-brand" />
            {engine.metric}
          </p>
        </div>

        <div className="flex items-center justify-center">
          <div className="w-full max-w-md">{engine.visual}</div>
        </div>
      </div>
    </ScrollReveal>
  );
}
