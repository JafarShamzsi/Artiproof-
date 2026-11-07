/**
 * Design tokens — single source for surface/text/brand/semantic class names,
 * spacing/typography/motion/radius scales.
 *
 * Use these for *consistency*, not as a replacement for local Tailwind. If a
 * component needs something one-off, use Tailwind directly. If three places
 * need the same thing, promote it here.
 *
 * Color scoring helpers (red/amber/emerald per score) live in `colors.ts` —
 * those depend on a numeric value, not a fixed semantic.
 */

// ============ COLOR TOKENS ============
export const colors = {
  surface: {
    primary: "bg-zinc-950",
    secondary: "bg-zinc-900",
    tertiary: "bg-zinc-800",
    elevated: "bg-zinc-900/80 backdrop-blur-xl",
  },
  text: {
    primary: "text-white",
    secondary: "text-zinc-400",
    tertiary: "text-zinc-500",
    inverse: "text-zinc-950",
  },
  brand: {
    primary: "text-emerald-400",
    primaryBg: "bg-emerald-500",
    primaryHover: "hover:bg-emerald-600",
    primaryGhost: "bg-emerald-500/10 text-emerald-400",
    primaryBorder: "border-emerald-500/20",
  },
  success: {
    text: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/20",
  },
  warning: {
    text: "text-amber-400",
    bg: "bg-amber-500/10",
    border: "border-amber-500/20",
  },
  error: {
    text: "text-red-400",
    bg: "bg-red-500/10",
    border: "border-red-500/20",
  },
  info: {
    text: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/20",
  },
  border: {
    default: "border-zinc-800",
    subtle: "border-zinc-800/50",
    strong: "border-zinc-700",
  },
} as const;

// ============ SPACING SCALE ============
// 4px base. Tailwind: 1=4px, 2=8px, 3=12px, 4=16px, 6=24px, 8=32px, 12=48px, 16=64px
export const spacing = {
  section: "py-24 md:py-32",
  sectionInner: "py-16 md:py-24",
  card: "p-6",
  cardCompact: "p-4",
  stack: "space-y-6",
  stackTight: "space-y-3",
  stackLoose: "space-y-12",
} as const;

// ============ TYPOGRAPHY SCALE ============
export const typography = {
  hero:
    "font-display text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight",
  sectionTitle: "font-display text-3xl sm:text-4xl font-bold tracking-tight",
  sectionSubtitle: "text-lg sm:text-xl text-zinc-400 max-w-2xl",
  eyebrow: "text-sm font-medium text-emerald-400 tracking-wide uppercase",
  pageTitle: "font-display text-2xl font-bold text-white",
  cardTitle: "text-sm font-medium text-zinc-300",
  cardValue: "text-2xl font-bold text-white",
  label: "text-xs font-medium text-zinc-500 uppercase tracking-wider",
  body: "text-sm text-zinc-400",
  caption: "text-xs text-zinc-500",
} as const;

// ============ MOTION TOKENS ============
// Cubic-bezier matches Linear's "out-expo" feel.
export const motion = {
  fast: { duration: 0.15, ease: [0.16, 1, 0.3, 1] as const },
  normal: { duration: 0.3, ease: [0.16, 1, 0.3, 1] as const },
  slow: { duration: 0.5, ease: [0.16, 1, 0.3, 1] as const },
  spring: { type: "spring" as const, stiffness: 300, damping: 30 },
} as const;

// ============ BORDER RADIUS ============
export const radius = {
  sm: "rounded-md",
  md: "rounded-lg",
  lg: "rounded-xl",
  xl: "rounded-2xl",
  full: "rounded-full",
} as const;
