# Design

> Visual system after the wine + amber rebuild.
> Update this file when colors, fonts, or component patterns change.

## Theme

**Both light and dark, with manual toggle + system fallback.**

Scene sentence (dark): *a 26-year-old PhD candidate in Baku reading a sample
fact-check report on a borrowed institutional laptop in a dim basement
library at 11pm, deciding whether to upload her dissertation draft.*

Scene sentence (light): *the head of a research integrity office at a
mid-sized regional university, projector on, demoing the comparison page
to her dean over lunch.*

Both registers matter. Light is not a desaturated inversion of dark — it's
a separately-tuned cream-and-wine palette with its own type weight choices
and its own contrast budget.

The toggle persists to `localStorage` under the key `artiproof-theme`
with values `"light" | "dark" | "system"`. Default is `"system"`. The
theme provider lives in a `"use client"` boundary at the root layout.

## Color

**Strategy: Restrained committed.** Wine carries the primary action and
brand emphasis (under 12% of visible surface). Amber appears in narrow,
deliberate places (Most Popular pricing badge, "misleading" verdict
chip). Score thresholds (high / mid / low → emerald / amber / red) stay
exactly as before because they're functional, not brand.

| Role | Dark | Light |
|---|---|---|
| Surface base | `#15100F` (charcoal-wine) | `#FBF7F3` (warm cream) |
| Surface card | `#1F1816` | `#FFFFFF` |
| Surface elevated | `#1F1816 / 80%` + `backdrop-blur-xl` | `#FFFFFF / 90%` + `backdrop-blur-xl` |
| Border subtle | `#3A2D2A / 50%` | `#E5DBD0 / 60%` |
| Border default | `#3A2D2A` | `#D9CDBE` |
| Border strong | `#5C4641` | `#B79E89` |
| Text primary | `#F5EBE5` (warm off-white) | `#1A0808` (deep wine-black) |
| Text secondary | `#B8A89E` | `#6B5048` |
| Text tertiary | `#8A7A70` | `#9C7E72` |
| Brand bg | `#A03434` (oxblood) | `#7C2828` (deeper oxblood) |
| Brand bg hover | `#B84747` | `#5C1F1F` |
| Brand text | `#D87979` (rose-tinged) | `#7C2828` |
| Accent (amber) | `#E8AA42` | `#C8901E` |
| Score: high (≥70) | `text-emerald-400` / stroke `#10b981` | `text-emerald-600` / stroke `#059669` |
| Score: mid (40–69) | `text-amber-400` / stroke `#f59e0b` | `text-amber-600` / stroke `#d97706` |
| Score: low (<40) | `text-red-400` / stroke `#ef4444` | `text-red-600` / stroke `#dc2626` |
| AI prob ≥0.7 | `bg-red-500` | `bg-red-600` |
| AI prob 0.4–0.69 | `bg-amber-500` | `bg-amber-600` |
| AI prob <0.4 | `bg-emerald-500` | `bg-emerald-600` |

Tokens are exposed as CSS variables (`--brand`, `--surface-base`,
`--text-primary`, etc.) defined under `:root` (light defaults) and
`html.dark` (dark overrides). Tailwind v4 reads them via `@theme inline`
in `globals.css`, so utility classes like `bg-brand` and `text-fg` are
theme-aware automatically.

Score color function (`lib/colors.ts`) is unchanged for high/mid/low but
returns theme-aware classes via Tailwind's `dark:` variants.

## Typography

- **Display** (`font-display`): **Fraunces**. Variable serif with optical
  sizing axis. Weights 400, 500, 600, 700, 800. Used on hero headline,
  every section h2, dashboard h1s, pricing tier names, score readouts in
  large gauges. Fraunces was chosen for the editorial, University-Press
  feel — wholly distinct from the Vercel-Geist or generic-sans-SaaS
  default.
- **Body** (`font-sans`): **Inter**. Weights 400, 500, 600. Body, table
  cells, captions, form labels, button text. Kept from the prior
  iteration because the legibility-on-body case was already strong.
- **Mono** (`font-mono`): **JetBrains Mono** (Google Font). Code samples,
  numeric IDs, ORCIDs, DOIs.

Scale (Tailwind classes used in the codebase):

| Size | Class | Usage |
|---|---|---|
| 12px | `text-xs` | Captions, source attributions, eyebrows |
| 14px | `text-sm` | Body, table cells, labels |
| 16px | `text-base` | Emphasized body, buttons |
| 18px | `text-lg` | Section subtitles |
| 20px | `text-xl` | Card titles |
| 24px | `text-2xl` | Dashboard page titles |
| 30px | `text-3xl` | Mini-FAQ heading, stat values |
| 36px | `text-4xl` | Section titles (mobile) |
| 48px | `text-5xl` | Section titles (desktop), hero (sm) |
| 60px | `text-6xl` | Hero (md) |
| 72px | `text-7xl` | Hero (lg+) |

Hierarchy rule: ≥ 1.25 ratio between adjacent steps within a single
block. `text-balance` on every h1/h2 to prevent orphan words.

## Spacing

4px Tailwind grid. Section vertical rhythm: `py-24 md:py-32` between
landing sections. Card padding: `p-6` (default) or `p-4` (compact).
Stack rhythm: `space-y-6` (normal), `space-y-3` (tight),
`space-y-12` (loose).

Container max-width: `max-w-7xl` for landing, `max-w-5xl` for pricing
and comparison, `max-w-3xl` for the FAQ block.

## Radius

| Token | Class | Usage |
|---|---|---|
| sm | `rounded-md` | Inputs |
| md | `rounded-lg` | Buttons, cards |
| lg | `rounded-xl` | Hero CTA, large cards, browser-chrome mockup |
| xl | `rounded-2xl` | Pricing cards, hero browser frame |
| full | `rounded-full` | Badges, status dots, score circles |

## Elevation

No drop shadows on neutral surfaces in dark. In light, cards use a soft
warm-tinted shadow (`shadow-[0_2px_16px_-4px_rgba(124,40,40,0.08)]`).

Two elevation strategies in use:

1. **Border + tint**: cards differentiate via tinted border + subtle
   surface tint. No shadow in dark.
2. **Brand glow**: `shadow-lg shadow-brand/20` on primary CTAs, plus
   the `cta-glow` utility (a `::after` blurred wine halo) on the hero
   and final-CTA buttons only.

## Motion

- Easing: cubic-bezier `[0.16, 1, 0.3, 1]` (out-expo). No bounce, no
  elastic.
- Tokens (`lib/design-tokens.ts`): `fast` 150ms, `normal` 300ms,
  `slow` 500ms.
- `FadeIn` wrapper: 500ms fade + 24px directional slide, viewport-once,
  honors `prefers-reduced-motion` (returns 0ms / no offset).
- `cta-glow` halo: 300ms opacity transition on hover/focus, opacity
  0.4 → 0.65.
- **Critical SSR rule:** the `initial` prop on every `motion.*`
  component must be invariant across server and client. Conditional
  `initial` on `useReducedMotion()` causes hydration mismatch. Express
  reduced-motion only via `transition.duration: reduce ? 0 : N`.
- Don't animate layout properties. Don't add bounce.

## Components

- **Button** (`components/ui/button.tsx`): variants `default`, `primary`
  (wine + brand glow shadow), `outline`, `secondary`, `ghost`,
  `destructive`, `link`. Sizes `xs`, `sm`, `default`, `lg`, `xl`, plus
  `icon-*`. Uses `@base-ui/react` + cva.
- **Card** (`components/ui/card.tsx`): shadcn-style. Default border +
  surface-card bg.
- **Score gauge** (`components/ui/score-gauge.tsx`): half-circle SVG, no
  animation library, `role="meter"`, label optional.
- **Empty state** (`components/ui/empty-state.tsx`): icon in tinted
  square, title + description + optional action button.
- **Breadcrumb** (`components/ui/breadcrumb.tsx`): chevron-separated,
  `aria-current="page"` on the leaf.
- **FadeIn** (`components/ui/fade-in.tsx`): viewport-once reveal wrapper.
- **ThemeToggle** (`components/ui/theme-toggle.tsx`): three-position
  toggle (Light / System / Dark) styled as a segmented control.

Landing-specific:

- `Navbar` — sticky, blurred, hides on scroll-down past 100px,
  active-section indicator via IntersectionObserver. Theme toggle on
  the right next to the auth buttons.
- `HeroSection` — outcome headline (Fraunces), browser-chrome product
  mockup with mock score + claim rows + AI bar, single primary CTA
  with `cta-glow`, honest pre-launch trust card.
- `TrustSection` — 4-stat sourced bar in a 4-up grid. No marquee, no
  count-up — `tabular-nums` static numbers with attribution.
- `ScannerPreview` — locked-input demo (three example chips only,
  no free-paste fallback). Pre-recorded results match the rubric of
  a real submission.
- `ComparisonSection` — feature ✓/✗ table with row hover, "Unique"
  badges on ArtiProof-only features, mobile card layout for narrow
  viewports.
- `FeaturesSection` — alternating L/R stacked rows per engine, one
  unique mini-visualization per engine (gauge / verdict rows /
  AI bars / citation network / h-index delta). NOT a uniform card
  grid.
- `PricingSection` — three tiers with quiet "Most popular" badge on
  Pro, mini-FAQ accordion below.
- `CTASection` — bordered wrapper card with soft radial backdrop.
- `Footer` — three columns of real links, regional tagline, legal row.
- Section dividers — gradient hairline `bg-gradient-to-r
  from-transparent via-border-default to-transparent`.

## Layout patterns

- Landing wraps every section in a thin gradient-hairline divider.
  No FadeIn-on-section because the section content has its own scroll
  reveals where appropriate.
- Dashboard pages start with `<h1>` in `font-display text-2xl`. Nested
  pages start with a `Breadcrumb` then page header.
- Score gauges and progress bars always pair the visual with an
  `aria-valuetext` so the meaning travels to assistive tech.

## Accessibility

- Skip-to-content target `<main id="main-content" tabIndex={-1}>`.
- Score circles use `role="meter"` with full ARIA value triplet.
- Progress bars use `role="progressbar"`.
- Live regions (`role="status" aria-live="polite" aria-atomic="true"`)
  announce SSE pipeline steps and theme changes for screen readers.
- `focus-visible` styling on every interactive element including SVG
  circles (Safari ignores `tabIndex` on `<g>`).
- Form labels associated via `htmlFor`.
- Contrast: ≥ 4.5:1 body / ≥ 3:1 large text in both modes.
- Theme toggle has `aria-pressed` per option and announces via the
  status live region.

## Anti-patterns to refuse

- No gradient text. No `background-clip: text` on headlines.
- No side-stripe borders > 1px on cards / alerts.
- No glassmorphism by default; the navbar blur and dialog blur are the
  only allowed exceptions.
- No identical card grids of icon + heading + 3 lines.
- No hero-metric template (big number / small label / supporting stats /
  gradient accent).
- No animated count-up gimmicks. Static `tabular-nums` is correct.
- No marquees, particle systems, falling-stars, or "ambient" continuous
  motion.
- No bounce / elastic easing.
