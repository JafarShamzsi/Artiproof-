"use client";

import { useRef } from "react";
import { motion, useInView } from "framer-motion";
import {
  Search,
  GraduationCap,
  Activity,
  Users,
  LayoutGrid,
  Code,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { SectionHeading } from "@/components/landing/shared/SectionHeading";
import { GlowCard } from "@/components/landing/shared/GlowCard";
import { ScrollReveal } from "@/components/landing/shared/ScrollReveal";
import { InteractiveGridPattern } from "@/components/landing/shared/InteractiveGridPattern";

/* ------------------------------------------------------------------ */
/*  Visual sub-components for each feature card                        */
/* ------------------------------------------------------------------ */

function ThreatGauge() {
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });

  const score = 87;
  // Arc goes from 180deg to 0deg (left to right semicircle)
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
        {/* Background arc */}
        <path
          d="M 10 60 A 40 40 0 0 1 110 60"
          fill="none"
          stroke="rgb(39, 39, 42)"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {/* Animated fill arc */}
        <motion.path
          d="M 10 60 A 40 40 0 0 1 110 60"
          fill="none"
          stroke="url(#gaugeGradient)"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={inView ? { strokeDashoffset: circumference - progress } : {}}
          transition={{ duration: 1.2, ease: "easeOut", delay: 0.3 }}
        />
        <defs>
          <linearGradient id="gaugeGradient" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#f59e0b" />
            <stop offset="50%" stopColor="#ef4444" />
            <stop offset="100%" stopColor="#dc2626" />
          </linearGradient>
        </defs>
      </svg>
      <motion.span
        className="mt-1 text-2xl font-bold text-red-400"
        initial={{ opacity: 0 }}
        animate={inView ? { opacity: 1 } : {}}
        transition={{ delay: 0.8 }}
      >
        {score}%
      </motion.span>
      <span className="text-xs text-zinc-500">Threat Score</span>
    </div>
  );
}

function ProgressVisual() {
  return (
    <div className="mt-4 space-y-2">
      <div className="h-2 w-full rounded-full bg-zinc-800">
        <div className="h-2 w-2/3 rounded-full bg-emerald-500" />
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xs text-zinc-500">Progress</span>
        <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-400">
          Level 5
        </span>
      </div>
    </div>
  );
}

function Sparkline() {
  return (
    <div className="mt-4">
      <svg width="100%" height="40" viewBox="0 0 200 40" preserveAspectRatio="none">
        <path
          d="M 0 35 Q 20 30, 40 28 T 80 20 T 120 22 T 160 10 T 200 5"
          fill="none"
          stroke="rgb(16, 185, 129)"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <path
          d="M 0 35 Q 20 30, 40 28 T 80 20 T 120 22 T 160 10 T 200 5 L 200 40 L 0 40 Z"
          fill="url(#sparklineFill)"
          opacity="0.15"
        />
        <defs>
          <linearGradient id="sparklineFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgb(16, 185, 129)" />
            <stop offset="100%" stopColor="transparent" />
          </linearGradient>
        </defs>
      </svg>
    </div>
  );
}

function AvatarStack() {
  const avatars = [
    { initials: "AK", color: "bg-emerald-600" },
    { initials: "JL", color: "bg-emerald-700" },
    { initials: "SR", color: "bg-emerald-500" },
    { initials: "MN", color: "bg-violet-600" },
  ];

  return (
    <div className="mt-4 flex -space-x-2">
      {avatars.map((a) => (
        <div
          key={a.initials}
          className={cn(
            "flex h-8 w-8 items-center justify-center rounded-full border-2 border-zinc-900 text-[10px] font-semibold text-white",
            a.color
          )}
        >
          {a.initials}
        </div>
      ))}
      <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-zinc-900 bg-zinc-700 text-[10px] font-medium text-zinc-300">
        +12
      </div>
    </div>
  );
}

function DisarmGrid() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });

  const colors = [
    "bg-emerald-500",
    "bg-emerald-400",
    "bg-emerald-500",
    "bg-emerald-400",
    "bg-emerald-600",
    "bg-emerald-400",
    "bg-emerald-600",
    "bg-emerald-500",
    "bg-emerald-600",
    "bg-emerald-500",
    "bg-emerald-500",
    "bg-emerald-400",
    "bg-emerald-600",
    "bg-emerald-500",
    "bg-emerald-400",
    "bg-emerald-500",
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

function CodeSnippet() {
  return (
    <div className="mt-4 rounded-lg bg-zinc-900/80 p-3 font-mono text-xs text-zinc-300">
      <span className="text-emerald-400">curl</span>{" "}
      <span className="text-emerald-300">-X POST</span>{" "}
      <span className="text-zinc-400">\</span>
      <br />
      <span className="pl-4 text-zinc-300">example.invalid/v1/scan</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Features data                                                      */
/* ------------------------------------------------------------------ */

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
    icon: Search,
    title: "Multi-Engine Scanner",
    description:
      "Paste any claim, URL, or screenshot. Get instant analysis from 6 independent AI engines with confidence scores and source verification.",
    visual: <ThreatGauge />,
    colSpan: "lg:col-span-2",
    rowSpan: "lg:row-span-2",
    glowColor: "red",
  },
  {
    icon: GraduationCap,
    title: "Learn & Level Up",
    description:
      "Duolingo-style media literacy courses. Earn XP, maintain streaks, and collect badges.",
    visual: <ProgressVisual />,
    glowColor: "emerald",
  },
  {
    icon: Activity,
    title: "Live Threat Feed",
    description:
      "Real-time dashboard of trending misinformation campaigns and emerging narratives.",
    visual: <Sparkline />,
    glowColor: "emerald",
  },
  {
    icon: Users,
    title: "Community Verification",
    description:
      "Crowdsourced truth-checking with expert moderation and reputation systems.",
    visual: <AvatarStack />,
    glowColor: "emerald",
  },
  {
    icon: LayoutGrid,
    title: "DISARM Classification",
    description:
      "Professional threat classification using the MITRE ATT&CK equivalent for disinformation.",
    visual: <DisarmGrid />,
    glowColor: "emerald",
  },
  {
    icon: Code,
    title: "Developer API",
    description:
      "RESTful API for bulk scanning, webhook integrations, and custom workflows. Build misinformation detection into your pipeline.",
    visual: <CodeSnippet />,
    colSpan: "lg:col-span-3",
    glowColor: "emerald",
  },
];

/* ------------------------------------------------------------------ */
/*  FeaturesSection                                                    */
/* ------------------------------------------------------------------ */

export function FeaturesSection() {
  return (
    <section id="features" className="relative py-24 overflow-hidden">
      <div className="absolute inset-0 z-0 opacity-30 pointer-events-none">
        <InteractiveGridPattern width={50} height={50} squares={[28, 20]} />
      </div>
      <div className="relative z-10 mx-auto max-w-7xl px-6">
        <SectionHeading
          eyebrow="PLATFORM"
          title="Everything You Need"
          gradient="Need"
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
