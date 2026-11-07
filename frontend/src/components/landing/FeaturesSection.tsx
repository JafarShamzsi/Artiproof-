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

function CredibilityGauge() {
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });

  const score = 85;
  const radius = 40;
  const circumference = Math.PI * radius;
  const progress = (score / 100) * circumference;

  return (
    <div className="mt-6 flex flex-col items-center">
      <svg
        ref={ref}
        width="140"
        height="80"
        viewBox="0 0 120 70"
        className="overflow-visible"
      >
        <path
          d="M 10 60 A 40 40 0 0 1 110 60"
          fill="none"
          stroke="rgb(39, 39, 42)"
          strokeWidth="8"
          strokeLinecap="round"
        />
        <motion.path
          d="M 10 60 A 40 40 0 0 1 110 60"
          fill="none"
          stroke="#10b981"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={inView ? { strokeDashoffset: circumference - progress } : {}}
          transition={{ duration: 1.0, ease: "easeOut", delay: 0.2 }}
        />
      </svg>
      <motion.span
        className="mt-1 font-display text-3xl font-bold text-emerald-400"
        initial={{ opacity: 0 }}
        animate={inView ? { opacity: 1 } : {}}
        transition={{ delay: 0.7 }}
      >
        85
      </motion.span>
      <span className="text-[10px] uppercase tracking-wider text-zinc-500">
        Credibility score
      </span>
    </div>
  );
}

function ClaimVerdicts() {
  const verdicts = [
    { label: "Climate data accurate", verdict: "True", color: "text-emerald-300", bar: "bg-emerald-500" },
    { label: "Vaccine claim disputed", verdict: "False", color: "text-red-300", bar: "bg-red-500" },
    { label: "Source outdated (2017)", verdict: "Misleading", color: "text-amber-300", bar: "bg-amber-500" },
  ];
  return (
    <div className="mt-5 space-y-2">
      {verdicts.map((v) => (
        <div key={v.label} className="flex items-center gap-3">
          <span className={cn("h-2 w-2 shrink-0 rounded-full", v.bar)} />
          <span className="flex-1 truncate text-xs text-zinc-300">{v.label}</span>
          <span className={cn("text-[10px] uppercase tracking-wider", v.color)}>
            {v.verdict}
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
  ];

  return (
    <div ref={ref} className="mt-5 space-y-1.5">
      {paragraphs.map((p, i) => (
        <div key={p.label} className="flex items-center gap-2">
          <span className="w-6 font-mono text-[10px] text-zinc-500">
            {p.label}
          </span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-800">
            <motion.div
              className={cn(
                "h-full rounded-full",
                p.prob > 0.7 ? "bg-red-500" : "bg-emerald-500",
              )}
              initial={{ width: 0 }}
              animate={inView ? { width: `${p.prob * 100}%` } : {}}
              transition={{ delay: i * 0.08, duration: 0.6, ease: "easeOut" }}
            />
          </div>
          <span className="w-9 text-right font-mono text-[10px] text-zinc-500">
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
    <div
      ref={ref}
      className="mt-5 flex h-32 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950/50 p-2"
    >
      <svg viewBox="0 0 220 120" className="h-full w-full" aria-hidden="true">
        {[
          { x1: 110, y1: 60, x2: 50, y2: 30 },
          { x1: 110, y1: 60, x2: 50, y2: 90 },
          { x1: 110, y1: 60, x2: 170, y2: 30 },
          { x1: 110, y1: 60, x2: 170, y2: 90 },
          { x1: 50, y1: 30, x2: 50, y2: 90 },
          { x1: 50, y1: 30, x2: 170, y2: 30 },
          { x1: 50, y1: 90, x2: 170, y2: 90 },
          { x1: 170, y1: 30, x2: 170, y2: 90 },
        ].map((line, i) => (
          <motion.line
            key={i}
            {...line}
            stroke={i < 4 ? "rgb(63 63 70)" : "#ef4444"}
            strokeWidth="1"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={inView ? { pathLength: 1, opacity: i < 4 ? 0.6 : 0.5 } : {}}
            transition={{ delay: 0.2 + i * 0.05, duration: 0.5 }}
          />
        ))}
        {[
          { cx: 110, cy: 60, r: 6, color: "#10b981" },
          { cx: 50, cy: 30, r: 4, color: "#52525b" },
          { cx: 50, cy: 90, r: 4, color: "#52525b" },
          { cx: 170, cy: 30, r: 4, color: "#ef4444" },
          { cx: 170, cy: 90, r: 4, color: "#ef4444" },
        ].map((node, i) => (
          <motion.circle
            key={i}
            cx={node.cx}
            cy={node.cy}
            r={node.r}
            fill={node.color}
            initial={{ scale: 0 }}
            animate={inView ? { scale: 1 } : {}}
            transition={{ delay: 0.6 + i * 0.05 }}
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
    <div ref={ref} className="mt-5 space-y-3 font-mono text-xs">
      <div className="flex items-baseline justify-between">
        <span className="text-zinc-500">Reported h-index</span>
        <motion.span
          className="text-2xl font-bold text-zinc-300"
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ delay: 0.2 }}
        >
          42
        </motion.span>
      </div>
      <div className="border-t border-zinc-800/60" />
      <div className="flex items-baseline justify-between">
        <span className="text-emerald-400">Adjusted</span>
        <motion.span
          className="font-display text-3xl font-bold text-emerald-400"
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ delay: 0.4 }}
        >
          27
        </motion.span>
      </div>
      <p className="text-[10px] leading-relaxed text-zinc-500">
        After removing 312 self-citations and 84 ring citations across 18 papers.
      </p>
    </div>
  );
}

interface Feature {
  icon?: LucideIcon;
  title: string;
  description: string;
  visual?: React.ReactNode;
}

// Five engines, deliberately not uniform.
// The first card spans 2 cols / 2 rows and carries the largest visual.
// The next four are smaller cards. The regional commitment lives in a
// type-only band underneath, not in another grid card.
const features: Feature[] = [
  {
    icon: Shield,
    title: "Source verification",
    description:
      "Each factual claim is extracted, fact-checked, and scored against external databases. The credibility number is a sum of recorded deductions, not a black box.",
    visual: <CredibilityGauge />,
  },
  {
    icon: BookOpen,
    title: "Claim analysis",
    description:
      "Every claim gets a verdict and the source that backs it. No bulk percentage, just specific calls.",
    visual: <ClaimVerdicts />,
  },
  {
    icon: Brain,
    title: "AI content detection",
    description:
      "Per-paragraph probability with confidence levels, not a single yes-or-no for the whole document.",
    visual: <AIDetectionBars />,
  },
  {
    icon: GitBranch,
    title: "Citation rings",
    description:
      "Detect groups of researchers who inflate each other's citation counts through mutual references.",
    visual: <CitationNetwork />,
  },
  {
    icon: Users,
    title: "Adjusted h-index",
    description:
      "h-index and citation counts recomputed after removing self-citations and ring citations.",
    visual: <IntegrityDelta />,
  },
];

export function FeaturesSection() {
  return (
    <section id="features" className="py-24">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mb-12 max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">
            Five engines
          </p>
          <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-balance text-white sm:text-4xl">
            Each engine returns evidence, not a verdict
          </h2>
        </div>

        {/* First feature is the hero card — large, single-column on mobile,
            spans 2x2 on lg. Remaining four are smaller equal cards. */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3 lg:grid-rows-2">
          <ScrollReveal delay={0} className="lg:col-span-2 lg:row-span-2">
            <FeatureCard feature={features[0]} hero />
          </ScrollReveal>
          {features.slice(1).map((f, i) => (
            <ScrollReveal key={f.title} delay={0.05 + i * 0.05}>
              <FeatureCard feature={f} />
            </ScrollReveal>
          ))}
        </div>

        {/* Regional commitment — type-only band, deliberately not a card,
            so it reads as a statement rather than another feature tile. */}
        <ScrollReveal delay={0.3} className="mt-12">
          <div className="border-t border-zinc-800/60 pt-12">
            <p className="text-xs font-medium uppercase tracking-wider text-emerald-400">
              Built for the EaP region
            </p>
            <p className="mt-3 max-w-3xl font-display text-2xl font-semibold leading-snug text-white sm:text-3xl">
              Native Azerbaijani and Russian. Local compliance. Pricing that
              works for a regional university budget, not a US R1.
            </p>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}

function FeatureCard({
  feature,
  hero = false,
}: {
  feature: Feature;
  hero?: boolean;
}) {
  const Icon = feature.icon;
  return (
    <div
      className={cn(
        "h-full rounded-xl border border-zinc-800 bg-zinc-900/40 transition-colors hover:border-zinc-700",
        hero ? "p-7 lg:p-8" : "p-6",
      )}
    >
      {Icon && (
        <Icon
          className={cn(
            "text-emerald-400",
            hero ? "mb-4 h-6 w-6" : "mb-3 h-5 w-5",
          )}
          aria-hidden="true"
        />
      )}
      <h3
        className={cn(
          "font-semibold text-white",
          hero ? "font-display text-xl sm:text-2xl" : "text-base",
        )}
      >
        {feature.title}
      </h3>
      <p
        className={cn(
          "mt-2 leading-relaxed text-zinc-400",
          hero ? "text-base" : "text-sm",
        )}
      >
        {feature.description}
      </p>
      {feature.visual}
    </div>
  );
}
