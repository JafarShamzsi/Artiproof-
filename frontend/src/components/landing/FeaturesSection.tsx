"use client";

import { useRef } from "react";
import { motion, useInView } from "framer-motion";
import {
  Shield,
  Brain,
  BookOpen,
  Users,
  GitBranch,
  Heart,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { SectionHeading } from "@/components/landing/shared/SectionHeading";
import { GlowCard } from "@/components/landing/shared/GlowCard";
import { ScrollReveal } from "@/components/landing/shared/ScrollReveal";
import { InteractiveGridPattern } from "@/components/landing/shared/InteractiveGridPattern";

function CredibilityGauge() {
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });

  const score = 85;
  const radius = 40;
  const circumference = Math.PI * radius;
  const progress = (score / 100) * circumference;

  return (
    <div className="mt-4 flex flex-col items-center">
      <svg
        ref={ref}
        width="120"
        height="70"
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
          stroke="url(#credGaugeGradient)"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={inView ? { strokeDashoffset: circumference - progress } : {}}
          transition={{ duration: 1.2, ease: "easeOut", delay: 0.3 }}
        />
        <defs>
          <linearGradient id="credGaugeGradient" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#eab308" />
            <stop offset="100%" stopColor="#22c55e" />
          </linearGradient>
        </defs>
      </svg>
      <motion.span
        className="mt-1 text-2xl font-bold text-emerald-400"
        initial={{ opacity: 0 }}
        animate={inView ? { opacity: 1 } : {}}
        transition={{ delay: 0.8 }}
      >
        {score}/100
      </motion.span>
      <span className="text-xs text-zinc-500">Credibility Score</span>
    </div>
  );
}

function ClaimVerdicts() {
  return (
    <div className="mt-4 space-y-2">
      {[
        { label: "Climate data accurate", verdict: "true", color: "bg-emerald-500" },
        { label: "Vaccine claim disputed", verdict: "false", color: "bg-red-500" },
        { label: "Source outdated", verdict: "misleading", color: "bg-yellow-500" },
      ].map((item) => (
        <div key={item.label} className="flex items-center gap-2">
          <div className={cn("h-2 w-2 rounded-full", item.color)} />
          <span className="text-xs text-zinc-400 flex-1">{item.label}</span>
          <span className="text-[10px] text-zinc-500 uppercase">{item.verdict}</span>
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
    <div ref={ref} className="mt-4 space-y-1.5">
      {paragraphs.map((p, i) => (
        <div key={p.label} className="flex items-center gap-2">
          <span className="w-6 text-[10px] text-zinc-500">{p.label}</span>
          <div className="flex-1 h-3 bg-zinc-800 rounded-full overflow-hidden">
            <motion.div
              className={cn("h-full rounded-full", p.prob > 0.7 ? "bg-red-500" : "bg-emerald-500")}
              initial={{ width: 0 }}
              animate={inView ? { width: `${p.prob * 100}%` } : {}}
              transition={{ delay: i * 0.1, duration: 0.6 }}
            />
          </div>
          <span className="w-8 text-right text-[10px] text-zinc-500">{Math.round(p.prob * 100)}%</span>
        </div>
      ))}
    </div>
  );
}

function CitationNetwork() {
  return (
    <div className="mt-4 flex h-24 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-950/50">
      <div className="relative">
        {[0, 72, 144, 216, 288].map((angle, i) => {
          const rad = (angle * Math.PI) / 180;
          const x = Math.cos(rad) * 30;
          const y = Math.sin(rad) * 20;
          return (
            <div
              key={i}
              className={cn(
                "absolute h-3 w-3 rounded-full",
                i === 2 ? "bg-red-500" : "bg-emerald-500/60"
              )}
              style={{
                left: `calc(50% + ${x}px - 6px)`,
                top: `calc(50% + ${y}px - 6px)`,
              }}
            />
          );
        })}
        <div className="h-4 w-4 rounded-full bg-emerald-400" />
      </div>
    </div>
  );
}

function IntegrityGrid() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });

  const colors = [
    "bg-emerald-500", "bg-emerald-400", "bg-red-500", "bg-emerald-400",
    "bg-emerald-600", "bg-emerald-400", "bg-emerald-600", "bg-red-400",
    "bg-emerald-600", "bg-emerald-500", "bg-emerald-500", "bg-emerald-400",
    "bg-red-500", "bg-emerald-500", "bg-emerald-400", "bg-emerald-500",
  ];

  return (
    <div ref={ref} className="mt-4 grid grid-cols-4 gap-1">
      {colors.map((color, i) => (
        <motion.div
          key={i}
          className={cn("h-4 w-full rounded-sm", color)}
          initial={{ opacity: 0, scale: 0.5 }}
          animate={inView ? { opacity: 0.7, scale: 1 } : {}}
          transition={{ delay: i * 0.05, duration: 0.3 }}
        />
      ))}
    </div>
  );
}

function APISnippet() {
  return (
    <div className="mt-4 rounded-lg bg-zinc-900/80 p-3 font-mono text-xs text-zinc-300">
      <span className="text-emerald-400">POST</span>{" "}
      <span className="text-zinc-300">/api/source-check</span>
      <br />
      <span className="text-emerald-400">POST</span>{" "}
      <span className="text-zinc-300">/api/researcher/analyze</span>
    </div>
  );
}

interface Feature {
  icon: LucideIcon;
  title: string;
  description: string;
  visual: React.ReactNode;
  colSpan?: string;
  rowSpan?: string;
  glowColor?: string;
}

const features: Feature[] = [
  {
    icon: Shield,
    title: "Source Verification",
    description:
      "Paste a URL or text. Get claim-by-claim fact-checking powered by AI and verified databases. See credibility scores, detect misinformation, and get the true version.",
    visual: <CredibilityGauge />,
    colSpan: "lg:col-span-2",
    rowSpan: "lg:row-span-2",
    glowColor: "emerald",
  },
  {
    icon: BookOpen,
    title: "Claim Analysis",
    description:
      "Every factual claim is extracted, verified, and rated. Know exactly which parts of an article are accurate and which are misleading.",
    visual: <ClaimVerdicts />,
    glowColor: "emerald",
  },
  {
    icon: Brain,
    title: "AI Content Detection",
    description:
      "Identify AI-generated content paragraph by paragraph with per-section confidence scores.",
    visual: <AIDetectionBars />,
    glowColor: "emerald",
  },
  {
    icon: GitBranch,
    title: "Citation Ring Detection",
    description:
      "Expose groups of researchers who inflate each other's citation counts through mutual referencing patterns.",
    visual: <CitationNetwork />,
    glowColor: "emerald",
  },
  {
    icon: Users,
    title: "Honest Researcher Ratings",
    description:
      "Adjusted h-index and citation counts that account for manipulation. See the real impact of any researcher.",
    visual: <IntegrityGrid />,
    glowColor: "emerald",
  },
  {
    icon: Heart,
    title: "Built for the EaP Region",
    description:
      "Purpose-built for Azerbaijan and Eastern Partnership universities. Native Azerbaijani and Russian language support, local compliance, and pricing designed for the region.",
    visual: <APISnippet />,
    colSpan: "lg:col-span-3",
    glowColor: "emerald",
  },
];

export function FeaturesSection() {
  return (
    <section id="features" className="relative py-24 overflow-hidden">
      <div className="absolute inset-0 z-0 opacity-30 pointer-events-none">
        <InteractiveGridPattern width={50} height={50} squares={[28, 20]} />
      </div>
      <div className="relative z-10 mx-auto max-w-7xl px-6">
        <SectionHeading
          eyebrow="PLATFORM"
          title="Everything You Need for Research Integrity"
          gradient="Integrity"
        />

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {features.map((feature, i) => (
            <ScrollReveal
              key={feature.title}
              delay={i * 0.1}
              className={cn(feature.colSpan, feature.rowSpan)}
            >
              <GlowCard
                className="h-full p-6"
                glowColor={feature.glowColor}
              >
                <feature.icon className="mb-3 h-6 w-6 text-zinc-400" />
                <h3 className="text-lg font-semibold text-white">
                  {feature.title}
                </h3>
                <p className="mt-1 text-sm text-zinc-400">
                  {feature.description}
                </p>
                {feature.visual}
              </GlowCard>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}
