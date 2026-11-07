"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";
import { HeroGlobe } from "./HeroGlobe";
import { InteractiveHoverButton } from "./shared/InteractiveHoverButton";

const headlineWords = ["The", "Truth", "Has"];
const headlineLine2Words = ["a", "Guardian"];

const orbitingDots = [
  { size: 8, radius: 140, duration: 8, delay: 0, color: "bg-emerald-400" },
  { size: 6, radius: 160, duration: 12, delay: 2, color: "bg-emerald-400" },
  { size: 10, radius: 120, duration: 10, delay: 4, color: "bg-emerald-300" },
  { size: 5, radius: 170, duration: 14, delay: 1, color: "bg-emerald-300" },
] as const;

export function HeroSection() {
  const prefersReducedMotion = useReducedMotion();

  const animationProps = (delay: number) =>
    prefersReducedMotion
      ? {}
      : {
          initial: { opacity: 0, y: 40 } as const,
          animate: { opacity: 1, y: 0 } as const,
          transition: { duration: 0.5, delay, ease: "easeOut" as const },
        };

  const wordDelay = (index: number, lineOffset: number = 0) =>
    0.1 + (lineOffset + index) * 0.08;

  return (
    <section className="relative min-h-screen flex items-center overflow-hidden">
      {/* Subtle background gradient */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-zinc-950 via-zinc-950 to-zinc-900" />

      <div className="relative mx-auto w-full max-w-7xl px-6 py-20">
        <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-2">
          {/* Left — Text Content */}
          <div>
            {/* Eyebrow */}
            <motion.p
              {...animationProps(0)}
              className="text-xs uppercase tracking-[0.2em] text-emerald-400"
            >
              Misinformation Threat Intelligence
            </motion.p>

            {/* Headline Line 1 */}
            <h1 className="mt-6 text-5xl font-bold leading-tight text-white md:text-6xl lg:text-7xl">
              <span className="block">
                {headlineWords.map((word, i) => (
                  <motion.span
                    key={word}
                    className="inline-block mr-[0.25em]"
                    {...animationProps(wordDelay(i))}
                  >
                    {word}
                  </motion.span>
                ))}
              </span>

              {/* Headline Line 2 */}
              <span className="block">
                {headlineLine2Words.map((word, i) => (
                  <motion.span
                    key={word}
                    className={cn(
                      "inline-block mr-[0.25em]",
                      word === "Guardian" &&
                        "text-emerald-400"
                    )}
                    {...animationProps(wordDelay(i, headlineWords.length))}
                  >
                    {word}
                  </motion.span>
                ))}
              </span>
            </h1>

            {/* Subheadline */}
            <motion.p
              {...animationProps(0.6)}
              className="mt-6 max-w-lg text-xl text-zinc-400"
            >
              Multi-engine AI analysis. Real-time threat intelligence. The
              VirusTotal of misinformation — built for everyone.
            </motion.p>

            {/* CTA Buttons */}
            <motion.div
              {...animationProps(0.75)}
              className="mt-8 flex flex-col gap-4 sm:flex-row"
            >
              <InteractiveHoverButton
                text="Launch Scanner"
                href="/register"
                className="py-3 text-base"
              />
              <a
                href="#how-it-works"
                className="inline-flex items-center justify-center rounded-full border border-zinc-700 px-6 py-3 font-semibold text-zinc-300 transition-all hover:border-zinc-500 hover:text-white"
              >
                See How It Works
              </a>
            </motion.div>

            {/* Social Proof */}
            <motion.p
              {...animationProps(0.9)}
              className="mt-12 text-sm text-zinc-500"
            >
              Trusted by researchers at{" "}
              <span className="text-zinc-400">MIT</span> ·{" "}
              <span className="text-zinc-400">Stanford</span> ·{" "}
              <span className="text-zinc-400">Reuters</span> ·{" "}
              <span className="text-zinc-400">BBC Verify</span>
            </motion.p>
          </div>

          {/* Right — 3D Globe */}
          <div className="flex items-center justify-center">
            {prefersReducedMotion ? (
              <GlobePlaceholder reducedMotion />
            ) : (
              <HeroGlobe />
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Globe Placeholder (will be replaced with R3F globe)               */
/* ------------------------------------------------------------------ */

function GlobePlaceholder({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <div className="relative aspect-square w-48 md:w-80">
      {/* Glow background */}
      <div className="absolute inset-0 rounded-full bg-emerald-500/20 blur-2xl" />

      {/* Main circle with gradient border */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="relative h-48 w-48 rounded-full md:h-80 md:w-80">
          {/* Outer gradient ring */}
          <div className="absolute inset-0 rounded-full bg-emerald-500/30 p-px">
            <div className="h-full w-full rounded-full bg-zinc-950" />
          </div>

          {/* Inner subtle gradient */}
          <div className="absolute inset-2 rounded-full bg-emerald-500/5" />

          {/* Grid lines hint */}
          <div className="absolute inset-4 rounded-full border border-zinc-800/50" />
          <div className="absolute inset-8 rounded-full border border-zinc-800/30" />
          <div className="absolute inset-12 rounded-full border border-zinc-800/20" />

          {/* Center dot */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="h-2 w-2 rounded-full bg-emerald-400/60" />
          </div>
        </div>
      </div>

      {/* Orbiting dots */}
      {orbitingDots.map((dot, index) => (
        <OrbitingDot key={index} {...dot} reducedMotion={reducedMotion} />
      ))}
    </div>
  );
}

function OrbitingDot({
  size,
  radius,
  duration,
  delay,
  color,
  reducedMotion,
}: {
  size: number;
  radius: number;
  duration: number;
  delay: number;
  color: string;
  reducedMotion: boolean;
}) {
  if (reducedMotion) {
    // Static positioned dot when reduced motion is preferred
    const angle = delay * 45; // spread them out
    const rad = (angle * Math.PI) / 180;
    const x = Math.cos(rad) * (radius * 0.4);
    const y = Math.sin(rad) * (radius * 0.4);

    return (
      <div
        className="absolute left-1/2 top-1/2"
        style={{
          transform: `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))`,
        }}
      >
        <div
          className={cn("rounded-full opacity-60", color)}
          style={{ width: size, height: size }}
        />
      </div>
    );
  }

  return (
    <div className="absolute inset-0">
      <motion.div
        className="absolute left-1/2 top-1/2"
        animate={{
          rotate: 360,
        }}
        transition={{
          duration,
          delay,
          repeat: Infinity,
          ease: "linear",
        }}
        style={{
          width: radius * 2,
          height: radius * 2,
          marginLeft: -radius,
          marginTop: -radius,
        }}
      >
        <div
          className={cn("absolute rounded-full shadow-lg", color)}
          style={{
            width: size,
            height: size,
            top: 0,
            left: "50%",
            transform: "translateX(-50%)",
            boxShadow: `0 0 ${size * 2}px currentColor`,
          }}
        >
          <div
            className={cn("h-full w-full rounded-full opacity-60", color)}
          />
        </div>
      </motion.div>
    </div>
  );
}
