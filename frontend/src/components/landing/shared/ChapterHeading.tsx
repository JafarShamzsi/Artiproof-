"use client";

import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";

interface ChapterHeadingProps {
  /** Roman numeral / section index — e.g. "I", "II", "Coda". */
  numeral?: string;
  /** Small-caps eyebrow — e.g. "How it works". */
  eyebrow: string;
  /** Display title — supports an italic emphasis fragment. */
  title: React.ReactNode;
  /** Optional editorial subtitle in italic Newsreader. */
  subtitle?: React.ReactNode;
  /** Centered or left-aligned. Default: left. */
  align?: "left" | "center";
  className?: string;
  id?: string;
}

/** Editorial chapter heading: faint numeral + small-caps label + double
 *  rule + display title in Fraunces. The double rule is the visual
 *  signature of a research-paper section break. */
export function ChapterHeading({
  numeral,
  eyebrow,
  title,
  subtitle,
  align = "left",
  className,
  id,
}: ChapterHeadingProps) {
  const reduce = useReducedMotion();
  const centered = align === "center";

  return (
    <header
      id={id}
      className={cn(
        "relative",
        centered ? "mx-auto text-center" : "",
        "max-w-3xl",
        className,
      )}
    >
      {numeral && (
        <motion.span
          aria-hidden="true"
          initial={{ opacity: 0, x: reduce ? 0 : -8 }}
          whileInView={{ opacity: 0.45, x: 0 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: reduce ? 0 : 0.7, ease: [0.16, 1, 0.3, 1] }}
          className={cn(
            "numeral-chapter pointer-events-none absolute select-none",
            centered
              ? "left-1/2 -top-10 -translate-x-1/2"
              : "-left-2 -top-10 sm:-left-6 sm:-top-12 md:-left-14",
          )}
        >
          {numeral}
        </motion.span>
      )}

      <div
        className={cn(
          "flex items-center gap-3",
          centered && "justify-center",
        )}
      >
        <span aria-hidden="true" className="h-px w-7 bg-border-strong" />
        <span className="label-eyebrow text-brand-fg">{eyebrow}</span>
        <span aria-hidden="true" className="h-px flex-1 bg-border-strong sm:flex-initial sm:w-7" />
      </div>

      <h2 className="mt-6 font-display text-4xl font-semibold leading-[1.05] tracking-[-0.01em] text-balance text-fg-primary sm:text-5xl md:text-[3.5rem]">
        {title}
      </h2>

      {subtitle && (
        <p className="editorial-italic mt-5 max-w-2xl text-lg leading-relaxed sm:text-xl">
          {subtitle}
        </p>
      )}

      <hr className="rule-double-soft mt-9" />
    </header>
  );
}
