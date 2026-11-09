"use client";

import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";

interface MarginaliaProps {
  children: React.ReactNode;
  /** Side the annotation lives on. Affects bracket direction. */
  side?: "right" | "left";
  /** Optional bracket connecting margin → body. */
  bracket?: boolean;
  /** Optional small-caps label above the body. */
  label?: string;
  /** Optional rotation in deg for hand-drawn feel. */
  rotate?: number;
  /** Animation entry delay. */
  delay?: number;
  className?: string;
}

/** A right-margin annotation in the editorial voice. On wide screens,
 *  appears in the gutter; on narrow screens, falls back inline below
 *  the parent text. The bracket suggests a hand-drawn marginal note. */
export function Marginalia({
  children,
  side = "right",
  bracket = true,
  label,
  rotate = 0,
  delay = 0,
  className,
}: MarginaliaProps) {
  const reduce = useReducedMotion();

  return (
    <motion.aside
      initial={{ opacity: 0, x: reduce ? 0 : side === "right" ? -8 : 8 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true, amount: 0.5 }}
      transition={{
        duration: reduce ? 0 : 0.55,
        delay: reduce ? 0 : delay,
        ease: [0.16, 1, 0.3, 1],
      }}
      style={{ rotate: `${rotate}deg` }}
      className={cn(
        "relative flex max-w-[14rem] items-start gap-2",
        side === "left" && "flex-row-reverse",
        className,
      )}
    >
      {bracket && (
        <span
          aria-hidden="true"
          className={cn(
            "mt-2 hidden shrink-0 sm:block",
            side === "left" && "[transform:scaleX(-1)]",
          )}
        >
          <BracketSvg />
        </span>
      )}
      <div className={cn("min-w-0", side === "left" && "text-right")}>
        {label && (
          <span className="label-eyebrow mb-1 inline-block text-brand-fg">
            {label}
          </span>
        )}
        <div className="editorial-italic text-sm leading-snug text-fg-secondary">
          {children}
        </div>
      </div>
    </motion.aside>
  );
}

/** Hand-drawn-style angled bracket: short vertical stub + arrow into
 *  the body text. SVG so it stays crisp at any size. */
function BracketSvg() {
  return (
    <svg
      width="38"
      height="22"
      viewBox="0 0 38 22"
      fill="none"
      stroke="currentColor"
      strokeWidth="0.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-border-strong"
    >
      <path d="M 1 11 Q 6 11 12 6 T 26 11 L 36 11" />
      <path d="M 33 8 L 36.5 11 L 33 14" strokeWidth="0.7" />
    </svg>
  );
}
