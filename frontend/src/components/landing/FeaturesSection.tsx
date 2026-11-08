"use client";

import { useRef } from "react";
import { motion, useInView, useReducedMotion } from "framer-motion";
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
import { ChapterHeading } from "@/components/landing/shared/ChapterHeading";
import { FigurePlate } from "@/components/landing/shared/FigurePlate";

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
        width="220"
        height="120"
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
        {/* Tick marks */}
        {[0, 25, 50, 75, 100].map((p, i) => {
          const angle = Math.PI - (p / 100) * Math.PI;
          const x1 = 70 + Math.cos(angle) * 60;
          const y1 = 70 - Math.sin(angle) * 60;
          const x2 = 70 + Math.cos(angle) * 56;
          const y2 = 70 - Math.sin(angle) * 56;
          return (
            <line
              key={i}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke="currentColor"
              strokeWidth="0.6"
              className="text-fg-tertiary"
            />
          );
        })}
      </svg>
      <span className="-mt-9 font-display text-5xl font-semibold tabular-nums tracking-tight text-emerald-500 dark:text-emerald-400">
        {score}
      </span>
      <span className="label-eyebrow mt-2 text-fg-tertiary">
        Credibility · 0 to 100
      </span>
    </div>
  );
}

function ClaimVerdicts() {
  const verdicts = [
    {
      label: "Climate data accurate",
      v: "True",
      tone: "emerald",
      quote: "matches NOAA 2024 record",
    },
    {
      label: "Vaccine claim disputed",
      v: "False",
      tone: "red",
      quote: "study retracted Apr 2023",
    },
    {
      label: "Source outdated (2017)",
      v: "Misleading",
      tone: "amber",
      quote: "context lost in revision",
    },
  ];
  const toneColor = {
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
    <div className="space-y-2.5">
      {verdicts.map((v) => (
        <div
          key={v.label}
          className="rounded-sm border border-border-default bg-surface-base px-4 py-3"
        >
          <div className="flex items-center gap-3">
            <span
              className={cn(
                "h-1.5 w-1.5 shrink-0 rounded-full",
                toneDot[v.tone as keyof typeof toneDot],
              )}
            />
            <span className="flex-1 truncate text-sm text-fg-primary">
              {v.label}
            </span>
            <span
              className={cn(
                "font-mono text-[10px] uppercase tracking-[0.18em]",
                toneColor[v.tone as keyof typeof toneColor],
              )}
            >
              {v.v}
            </span>
          </div>
          <p className="editorial-italic mt-1.5 pl-4 text-xs text-fg-tertiary">
            {v.quote}
          </p>
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
    <div ref={ref} className="space-y-2.5 font-mono">
      {paragraphs.map((p, i) => (
        <div key={p.label} className="flex items-center gap-3">
          <span className="w-7 text-[10px] tracking-wider text-fg-tertiary">
            {p.label}
          </span>
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
          <span className="w-10 text-right text-[10px] tabular-nums tracking-wider text-fg-tertiary">
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
    <div ref={ref}>
      <svg viewBox="0 0 320 180" className="h-auto w-full" aria-hidden="true">
        {[
          { x1: 160, y1: 90, x2: 70, y2: 46, suspicious: false },
          { x1: 160, y1: 90, x2: 70, y2: 134, suspicious: false },
          { x1: 160, y1: 90, x2: 250, y2: 46, suspicious: false },
          { x1: 160, y1: 90, x2: 250, y2: 134, suspicious: false },
          { x1: 70, y1: 46, x2: 70, y2: 134, suspicious: false },
          { x1: 70, y1: 46, x2: 250, y2: 46, suspicious: true },
          { x1: 70, y1: 134, x2: 250, y2: 134, suspicious: true },
          { x1: 250, y1: 46, x2: 250, y2: 134, suspicious: true },
        ].map((line, i) => (
          <motion.line
            key={i}
            x1={line.x1}
            y1={line.y1}
            x2={line.x2}
            y2={line.y2}
            stroke={line.suspicious ? "#ef4444" : "currentColor"}
            strokeWidth={line.suspicious ? 1.5 : 1}
            strokeDasharray={line.suspicious ? "0" : "3 3"}
            className={line.suspicious ? "" : "text-border-strong"}
            initial={{ pathLength: 0, opacity: 0 }}
            animate={
              inView
                ? { pathLength: 1, opacity: line.suspicious ? 0.85 : 0.55 }
                : {}
            }
            transition={{ delay: 0.2 + i * 0.05, duration: 0.6 }}
          />
        ))}
        {[
          { cx: 160, cy: 90, r: 8, color: "var(--brand)", label: "P" },
          { cx: 70, cy: 46, r: 5, color: "currentColor", className: "text-fg-tertiary" },
          { cx: 70, cy: 134, r: 5, color: "currentColor", className: "text-fg-tertiary" },
          { cx: 250, cy: 46, r: 5, color: "#ef4444", label: "R" },
          { cx: 250, cy: 134, r: 5, color: "#ef4444", label: "R" },
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
              delay: 0.6 + i * 0.06,
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
  const reduce = useReducedMotion();

  return (
    <div ref={ref} className="space-y-5 font-mono">
      <div className="flex items-baseline justify-between">
        <span className="label-eyebrow text-fg-tertiary">
          h-index · reported
        </span>
        <motion.span
          className="text-2xl font-bold tabular-nums text-fg-secondary line-through decoration-border-strong decoration-1"
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ delay: reduce ? 0 : 0.2, duration: 0.4 }}
        >
          42
        </motion.span>
      </div>

      <div className="border-t border-border-subtle" />

      <div className="flex items-baseline justify-between">
        <span className="label-eyebrow text-brand-fg">
          h-index · adjusted
        </span>
        <motion.span
          className="font-display text-4xl font-semibold tabular-nums tracking-tight text-brand-fg"
          initial={{ opacity: 0, y: reduce ? 0 : 8 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: reduce ? 0 : 0.5, duration: 0.4 }}
        >
          27
        </motion.span>
      </div>

      <p className="editorial-italic font-sans text-xs leading-relaxed text-fg-tertiary">
        Illustrative reported and adjusted metrics. Estimates depend on
        the sampled citation data and require review.
      </p>
    </div>
  );
}

// ─── Engine spec ────────────────────────────────────────────────────────

const romans = ["I", "II", "III", "IV", "V"] as const;

interface Engine {
  icon: LucideIcon;
  eyebrow: string;
  title: string;
  description: string;
  metric: string;
  visual: React.ReactNode;
  caption: string;
}

const engines: Engine[] = [
  {
    icon: Shield,
    eyebrow: "Source verification",
    title: "Inspect the claims selected for review.",
    description:
      "Selected claims are compared with existing fact-checks and analyzed by a language model. Inspect the verdict, explanation and available links; a result may remain unverified.",
    metric: "Verifies claims against the Google Fact Check API",
    visual: <CredibilityGauge />,
    caption: "Illustrative score display. A numeric result does not certify accuracy.",
  },
  {
    icon: BookOpen,
    eyebrow: "Claim analysis",
    title: "Read the verdicts, not a percentage.",
    description:
      "True, false, misleading, partially true, or unverified. Available source links help you investigate a verdict; model-generated explanations are not independently verified evidence.",
    metric: "Up to 15 claims per submission",
    visual: <ClaimVerdicts />,
    caption: "Illustrative claim verdicts and explanations, not a completed analysis.",
  },
  {
    icon: Brain,
    eyebrow: "AI content detection",
    title: "Inspect paragraph-level style signals.",
    description:
      "The model estimates AI likelihood from a sample of paragraphs, with a heuristic fallback when unavailable. These style signals can be wrong and do not establish authorship.",
    metric: "Analyzes up to 20 paragraphs per document",
    visual: <AIDetectionBars />,
    caption: "Paragraph-by-paragraph AI signal, in mono — bars over 70% are flagged red.",
  },
  {
    icon: GitBranch,
    eyebrow: "Citation patterns",
    title: "Explore frequent citing authors.",
    description:
      "Researcher analysis samples incoming citation relationships. A concentration of citing authors can guide further review; it does not establish reciprocal citation rings or manipulation.",
    metric: "Incoming citation samples, not proof of a ring",
    visual: <CitationNetwork />,
    caption: "Illustrative network diagram, not evidence of an observed citation ring.",
  },
  {
    icon: Users,
    eyebrow: "Researcher integrity",
    title: "Compare reported and estimated metrics.",
    description:
      "A separate researcher lookup collects publication metrics and estimates adjustments from sampled citation data. Adjusted h-index values are estimates, not a paper-by-paper recomputation.",
    metric: "Reported metrics alongside estimates",
    visual: <IntegrityDelta />,
    caption: "Illustrative reported and adjusted h-index. The difference is not proof of misconduct.",
  },
];

// ─── Section ────────────────────────────────────────────────────────────

export function FeaturesSection() {
  return (
    <section id="features" className="py-28 sm:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <ChapterHeading
          numeral="III"
          eyebrow="Five engines"
          title={
            <>
              Each engine returns{" "}
              <span className="italic text-brand-fg">evidence,</span> not a verdict.
            </>
          }
          subtitle="Source checks and researcher lookups answer different questions. These examples illustrate the tools; inspect the actual findings and coverage in each analysis."
        />

        <div className="mt-24 space-y-28 md:space-y-36">
          {engines.map((engine, i) => (
            <EngineRow
              key={engine.eyebrow}
              engine={engine}
              flip={i % 2 === 1}
              chapterNumeral={romans[i]}
              chapterIndex={i + 1}
            />
          ))}
        </div>

        {/* Regional commitment — typographic statement, framed as a colophon. */}
        <ScrollReveal delay={0.1} className="mt-32">
          <div className="border-t border-border-subtle pt-12">
            <div className="flex items-center gap-3">
              <span aria-hidden="true" className="h-px w-7 bg-border-strong" />
              <span className="label-eyebrow text-brand-fg">
                Built for the EaP region
              </span>
            </div>
            <p className="mt-5 max-w-3xl font-display text-2xl font-medium leading-snug text-balance text-fg-primary sm:text-3xl">
              Native Azerbaijani and Russian. Local compliance. Pricing that
              works for a regional university budget — <span className="italic text-brand-fg">not a US R1.</span>
            </p>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}

function EngineRow({
  engine,
  flip,
  chapterNumeral,
  chapterIndex,
}: {
  engine: Engine;
  flip: boolean;
  chapterNumeral: string;
  chapterIndex: number;
}) {
  const Icon = engine.icon;
  return (
    <ScrollReveal>
      <div
        className={cn(
          "grid grid-cols-1 items-center gap-12 lg:grid-cols-2 lg:gap-20",
          flip && "lg:[&>:first-child]:order-2",
        )}
      >
        <div className="relative">
          {/* Faint chapter numeral floating in the margin */}
          <span
            aria-hidden="true"
            className="numeral-chapter pointer-events-none absolute -top-12 -left-1 select-none lg:-left-12 lg:-top-8"
          >
            {chapterNumeral}
          </span>

          <div className="flex items-center gap-3">
            <Icon
              className="h-4 w-4 text-brand-fg"
              strokeWidth={1.5}
              aria-hidden="true"
            />
            <span className="label-eyebrow text-brand-fg">
              Chapter {chapterNumeral} · {engine.eyebrow}
            </span>
          </div>

          <h3 className="mt-4 font-display text-3xl font-semibold leading-[1.05] tracking-[-0.01em] text-balance text-fg-primary sm:text-4xl md:text-[2.65rem]">
            {engine.title}
          </h3>

          <p className="measure mt-6 text-base leading-[1.7] text-fg-secondary sm:text-[17px]">
            {engine.description}
          </p>

          <p className="mt-7 inline-flex items-center gap-2.5 rounded-sm border border-border-default bg-surface-card px-3 py-1.5 text-xs text-fg-primary">
            <span className="h-1 w-1 rounded-full bg-brand" />
            <span className="font-mono uppercase tracking-[0.14em] text-[10px] text-fg-tertiary">
              Method ·
            </span>
            <span className="text-fg-primary">{engine.metric}</span>
          </p>
        </div>

        <div className="flex items-center justify-center">
          <FigurePlate
            index={`Plate ${chapterNumeral}`}
            caption={engine.caption}
            source={`Fig. ${chapterIndex} · synthesized output`}
            className="w-full max-w-md"
          >
            {engine.visual}
          </FigurePlate>
        </div>
      </div>
    </ScrollReveal>
  );
}
