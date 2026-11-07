import { scoreStroke } from "@/lib/colors";
import { cn } from "@/lib/utils";

interface ScoreGaugeProps {
  /** 0-100 score. Null/undefined renders an indeterminate gauge. */
  score: number | null | undefined;
  /** Pixel size of the SVG (also drives stroke + text scaling). */
  size?: number;
  /** Optional bottom label (e.g. "Credibility"). */
  label?: string;
  className?: string;
}

/**
 * Half-circle radial score gauge. Pure SVG (no animation library) so it
 * renders during SSR and respects reduced-motion automatically.
 *
 * Threshold colors match `scoreStroke` from lib/colors.ts:
 *   >= 70 emerald, >= 40 amber, < 40 red, null → muted zinc.
 */
export function ScoreGauge({
  score,
  size = 120,
  label,
  className,
}: ScoreGaugeProps) {
  const stroke = 8;
  const radius = (size - stroke * 2) / 2;
  const cx = size / 2;
  const cy = size / 2 + stroke;
  const startX = cx - radius;
  const endX = cx + radius;
  const arcPath = `M ${startX} ${cy} A ${radius} ${radius} 0 0 1 ${endX} ${cy}`;
  const arcLength = Math.PI * radius;

  const clampedScore =
    score == null ? 0 : Math.max(0, Math.min(100, score));
  const offset = arcLength - (clampedScore / 100) * arcLength;
  const color = scoreStroke(score);
  const isUnknown = score == null;

  const viewHeight = size / 2 + stroke * 2 + (label ? 20 : 0);

  return (
    <div className={cn("inline-flex flex-col items-center", className)}>
      <svg
        width={size}
        height={viewHeight}
        viewBox={`0 0 ${size} ${viewHeight}`}
        role="meter"
        aria-valuenow={isUnknown ? undefined : Math.round(clampedScore)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuetext={
          isUnknown
            ? "Score unavailable"
            : `${Math.round(clampedScore)} out of 100${label ? ` ${label.toLowerCase()}` : ""}`
        }
        aria-label={label || "Score"}
      >
        {/* Background arc */}
        <path
          d={arcPath}
          fill="none"
          stroke="rgb(63 63 70)" // zinc-700
          strokeWidth={stroke}
          strokeLinecap="round"
          opacity={0.5}
        />
        {/* Score arc */}
        {!isUnknown && (
          <path
            d={arcPath}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={arcLength}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 600ms ease-out" }}
          />
        )}
        {/* Score number */}
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          className="fill-white font-bold"
          style={{ fontSize: Math.round(size * 0.28) }}
        >
          {isUnknown ? "—" : Math.round(clampedScore)}
        </text>
        {label && (
          <text
            x={cx}
            y={cy + 16}
            textAnchor="middle"
            className="fill-zinc-500"
            style={{ fontSize: Math.round(size * 0.1) }}
          >
            {label}
          </text>
        )}
      </svg>
    </div>
  );
}
