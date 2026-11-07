"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { HeroGlobe } from "./HeroGlobe";
import { InteractiveHoverButton } from "./shared/InteractiveHoverButton";

const headlineWords = ["Research"];
const headlineLine2Words = ["Integrity", "Platform"];

export function HeroSection() {
  const animationProps = (delay: number) => ({
    initial: { opacity: 0, y: 40 } as const,
    animate: { opacity: 1, y: 0 } as const,
    transition: { duration: 0.5, delay, ease: "easeOut" as const },
  });

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
              Protecting Academic Integrity
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
                      word === "Platform" &&
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
              Verify sources for misinformation, detect AI-generated content,
              and expose citation manipulation in academic research. Protect the
              integrity of knowledge.
            </motion.p>

            {/* CTA Buttons */}
            <motion.div
              {...animationProps(0.75)}
              className="mt-8 flex flex-col gap-4 sm:flex-row"
            >
              <InteractiveHoverButton
                text="Check a Source"
                href="/register"
                className="py-3 text-base"
              />
              <a
                href="#how-it-works"
                className="inline-flex items-center justify-center rounded-full border border-zinc-700 px-6 py-3 font-semibold text-zinc-300 transition-all hover:border-zinc-500 hover:text-white"
              >
                Learn How It Works
              </a>
            </motion.div>

            {/* Social Proof */}
            <motion.p
              {...animationProps(0.9)}
              className="mt-12 text-sm text-zinc-500"
            >
              Built for{" "}
              <span className="text-zinc-400">researchers</span>,{" "}
              <span className="text-zinc-400">faculty</span>, and{" "}
              <span className="text-zinc-400">institutions</span> worldwide
            </motion.p>
          </div>

          {/* Right — Animated Globe */}
          <div className="flex items-center justify-center">
            <HeroGlobe />
          </div>
        </div>
      </div>
    </section>
  );
}

