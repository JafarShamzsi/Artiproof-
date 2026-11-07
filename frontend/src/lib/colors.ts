/**
 * Centralized color helpers for credibility / integrity scores so the
 * thresholds stay consistent across pages.
 *
 * Threshold convention (used everywhere):
 *   >= 70 → emerald (good)
 *   >= 40 → amber  (warn)
 *    < 40 → red    (bad)
 *   null / undefined → muted zinc
 */

/** 0-100 score → text color class. Null → muted. */
export function scoreColor(score: number | null | undefined): string {
  if (score == null) return "text-zinc-400";
  if (score >= 70) return "text-emerald-400";
  if (score >= 40) return "text-amber-400";
  return "text-red-400";
}

/** 0-100 score → background color class for progress bars / pills. */
export function scoreBgColor(score: number | null | undefined): string {
  if (score == null) return "bg-zinc-600";
  if (score >= 70) return "bg-emerald-500";
  if (score >= 40) return "bg-amber-500";
  return "bg-red-500";
}

/** 0-100 score → translucent border class (e.g. card outlines). */
export function scoreBorderColor(score: number | null | undefined): string {
  if (score == null) return "border-zinc-700";
  if (score >= 70) return "border-emerald-500/40";
  if (score >= 40) return "border-amber-500/40";
  return "border-red-500/40";
}

/** 0-100 score → solid border class (used for score gauge rings). */
export function scoreSolidBorderColor(
  score: number | null | undefined,
): string {
  if (score == null) return "border-zinc-600";
  if (score >= 70) return "border-emerald-500";
  if (score >= 40) return "border-amber-500";
  return "border-red-500";
}

/** 0-100 score → SVG hex stroke (for canvas / inline SVG that can't take Tailwind). */
export function scoreStroke(score: number | null | undefined): string {
  if (score == null) return "#52525b"; // zinc-600
  if (score >= 70) return "#10b981"; // emerald-500
  if (score >= 40) return "#f59e0b"; // amber-500
  return "#ef4444"; // red-500
}

/** AI-probability (0..1) → background color class for the heat bar. */
export function aiProbColor(prob: number | null | undefined): string {
  if (prob == null) return "bg-zinc-600";
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
      return "text-emerald-400";
    case "false":
      return "text-red-400";
    case "misleading":
    case "partially_true":
      return "text-amber-400";
    case "unverified":
    default:
      return "text-zinc-400";
  }
}
