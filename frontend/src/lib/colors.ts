/**
 * Centralized color helpers for credibility / integrity scores so the
 * thresholds stay consistent across pages.
 *
 * Threshold convention (used everywhere):
 *   >= 70 → emerald (good)
 *   >= 40 → amber  (warn)
 *    < 40 → red    (bad)
 *   null / undefined → muted (theme-aware)
 *
 * NOTE: score colors are SEMANTIC, not brand. They stay
 * red/amber/emerald regardless of the brand color (currently wine).
 * "High score" needs to read as "good" universally.
 */

/** 0-100 score → text color class. Null → muted, theme-aware.
 *  Uses 600/700 in light mode for ≥3:1 contrast against white card surfaces;
 *  400 in dark mode where the surface is near-black. */
export function scoreColor(score: number | null | undefined): string {
  if (score == null) return "text-fg-tertiary";
  if (score >= 70) return "text-emerald-700 dark:text-emerald-400";
  if (score >= 40) return "text-amber-700 dark:text-amber-400";
  return "text-red-700 dark:text-red-400";
}

/** 0-100 score → background color class for progress bars / pills. */
export function scoreBgColor(score: number | null | undefined): string {
  if (score == null) return "bg-border-strong";
  if (score >= 70) return "bg-emerald-500";
  if (score >= 40) return "bg-amber-500";
  return "bg-red-500";
}

/** 0-100 score → translucent border class (e.g. card outlines). */
export function scoreBorderColor(score: number | null | undefined): string {
  if (score == null) return "border-border-default";
  if (score >= 70) return "border-emerald-500/40";
  if (score >= 40) return "border-amber-500/40";
  return "border-red-500/40";
}

/** 0-100 score → solid border class (used for score gauge rings).
 *  Light mode uses 600 (≥3:1 vs white); dark stays 500. */
export function scoreSolidBorderColor(
  score: number | null | undefined,
): string {
  if (score == null) return "border-border-strong";
  if (score >= 70) return "border-emerald-600 dark:border-emerald-500";
  if (score >= 40) return "border-amber-600 dark:border-amber-500";
  return "border-red-600 dark:border-red-500";
}

/** 0-100 score → SVG hex stroke (for canvas / inline SVG that can't take Tailwind). */
export function scoreStroke(score: number | null | undefined): string {
  if (score == null) return "#71717a"; // neutral
  if (score >= 70) return "#10b981"; // emerald-500
  if (score >= 40) return "#f59e0b"; // amber-500
  return "#ef4444"; // red-500
}

/** AI-probability (0..1) → background color class for the heat bar. */
export function aiProbColor(prob: number | null | undefined): string {
  if (prob == null) return "bg-border-strong";
  if (prob >= 0.7) return "bg-red-500";
  if (prob >= 0.4) return "bg-amber-500";
  return "bg-emerald-500";
}

/** Verdict label → semantic color class. */
export function verdictColor(
  verdict: string | null | undefined,
): string {
  switch (verdict) {
    case "true":
      return "text-emerald-700 dark:text-emerald-400";
    case "false":
      return "text-red-700 dark:text-red-400";
    case "misleading":
    case "partially_true":
      return "text-amber-700 dark:text-amber-400";
    case "unverified":
    default:
      return "text-fg-secondary";
  }
}
