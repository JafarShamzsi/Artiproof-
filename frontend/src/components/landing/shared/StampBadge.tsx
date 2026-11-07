"use client";

import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";

interface StampBadgeProps {
  /** Either text (rectangular stamp) or a number (circle). */
  children: React.ReactNode;
  /** Round = credibility-score stamp; rect = "VERIFIED" / "RETRACTED". */
  shape?: "rect" | "circle";
  /** Slight per-instance rotation override (deg). Defaults to -6 / -3. */
  rotate?: number;
  className?: string;
  /** Override stamp brand color via CSS color string for semantic verdicts
   *  (e.g. red for "RETRACTED"). Falls back to brand wine. */
  tone?: "wine" | "emerald" | "red" | "amber";
  /** Whether to play the landing animation. Default true. */
  animate?: boolean;
  /** Optional caption underneath, rendered in editorial italic. */
  caption?: React.ReactNode;
  /** Pixel size for circle variant. */
  size?: number;
}

const toneStyles = {
  wine: { color: "var(--brand)", soft: "var(--brand-soft)" },
  emerald: { color: "#047857", soft: "#D1FAE5" },
  red: { color: "#B91C1C", soft: "#FEE2E2" },
  amber: { color: "#A16207", soft: "#FEF3C7" },
} as const;

/** A rubber-stamp verdict mark. The animation lands the stamp at a
 *  rotation, suggesting the imprint of an inked stamp on paper. */
export function StampBadge({
  children,
  shape = "rect",
  rotate,
  className,
  tone = "wine",
  animate = true,
  caption,
  size = 88,
}: StampBadgeProps) {
  const reduce = useReducedMotion();
  const t = toneStyles[tone];
  const finalRotate = rotate ?? (shape === "circle" ? -6 : -3);

  const isCircle = shape === "circle";

  return (
    <div className={cn("inline-flex flex-col items-center gap-2", className)}>
      <motion.span
        initial={
          animate && !reduce
            ? { opacity: 0, rotate: 0, scale: 1.4 }
            : { opacity: 1, rotate: finalRotate, scale: 1 }
        }
        whileInView={
          animate && !reduce ? { opacity: 1, rotate: finalRotate, scale: 1 } : {}
        }
        viewport={{ once: true, amount: 0.6 }}
        transition={{
          duration: reduce ? 0 : 0.55,
          ease: [0.16, 1, 0.3, 1],
        }}
        style={{
          ["--brand" as string]: t.color,
          ["--brand-soft" as string]: t.soft,
          ["--brand-fg" as string]: t.color,
          ...(isCircle ? { width: size, height: size } : {}),
        }}
        className={cn(
          isCircle ? "stamp-circle" : "stamp",
          isCircle ? "text-2xl" : "text-[10px]",
        )}
      >
        {children}
      </motion.span>
      {caption && (
        <span className="editorial-italic text-xs text-fg-tertiary">
          {caption}
        </span>
      )}
    </div>
  );
}
