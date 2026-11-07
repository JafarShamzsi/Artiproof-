import { Sparkles, ShieldCheck, AlertTriangle, XCircle, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ScoreExplanation, ScoreTone } from "@/lib/scoreExplanation";

const TONE_STYLES: Record<
  ScoreTone,
  { card: string; label: string; icon: typeof ShieldCheck; iconClass: string; pill: string }
> = {
  excellent: {
    card: "border-emerald-500/30 bg-emerald-500/5",
    label: "text-emerald-300",
    icon: Sparkles,
    iconClass: "text-emerald-300",
    pill: "bg-emerald-500/20 text-emerald-300",
  },
  good: {
    card: "border-emerald-500/20 bg-emerald-500/5",
    label: "text-emerald-300",
    icon: ShieldCheck,
    iconClass: "text-emerald-300",
    pill: "bg-emerald-500/20 text-emerald-300",
  },
  fair: {
    card: "border-amber-500/30 bg-amber-500/5",
    label: "text-amber-300",
    icon: Info,
    iconClass: "text-amber-300",
    pill: "bg-amber-500/20 text-amber-300",
  },
  poor: {
    card: "border-red-500/30 bg-red-500/5",
    label: "text-red-300",
    icon: AlertTriangle,
    iconClass: "text-red-300",
    pill: "bg-red-500/20 text-red-300",
  },
  critical: {
    card: "border-red-500/40 bg-red-500/10",
    label: "text-red-300",
    icon: XCircle,
    iconClass: "text-red-300",
    pill: "bg-red-500/20 text-red-300",
  },
};

interface ScoreExplanationCardProps {
  explanation: ScoreExplanation;
  className?: string;
}

export function ScoreExplanationCard({
  explanation,
  className,
}: ScoreExplanationCardProps) {
  const style = TONE_STYLES[explanation.tone];
  const Icon = style.icon;

  return (
    <div
      className={cn(
        "rounded-lg border p-4",
        style.card,
        className
      )}
    >
      <div className="flex items-center gap-2">
        <Icon className={cn("h-4 w-4 shrink-0", style.iconClass)} />
        <p className={cn("text-sm font-semibold", style.label)}>
          {explanation.label}
        </p>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-zinc-200">
        {explanation.summary}
      </p>
      {explanation.reasons.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-zinc-300">
          {explanation.reasons.map((reason, i) => (
            <li key={i} className="flex items-start gap-1.5">
              <span className={cn("mt-[5px] h-1 w-1 shrink-0 rounded-full", style.iconClass.replace("text-", "bg-"))} />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface ScoreExplanationCompactProps {
  explanation: ScoreExplanation;
  className?: string;
}

export function ScoreExplanationCompact({
  explanation,
  className,
}: ScoreExplanationCompactProps) {
  const style = TONE_STYLES[explanation.tone];
  const Icon = style.icon;
  const topReason = explanation.reasons[0];

  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2",
        style.card,
        className
      )}
    >
      <div className="flex items-center gap-1.5">
        <Icon className={cn("h-3 w-3 shrink-0", style.iconClass)} />
        <p className={cn("text-[11px] font-semibold uppercase tracking-wide", style.label)}>
          {explanation.label}
        </p>
      </div>
      {topReason && (
        <p className="mt-1 text-[11px] leading-snug text-zinc-200">{topReason}</p>
      )}
    </div>
  );
}

interface ScoreLabelProps {
  explanation: ScoreExplanation;
  className?: string;
}

export function ScoreLabel({ explanation, className }: ScoreLabelProps) {
  const style = TONE_STYLES[explanation.tone];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-[1px] text-[10px] font-semibold uppercase tracking-wide",
        style.pill,
        className
      )}
    >
      {explanation.label}
    </span>
  );
}
