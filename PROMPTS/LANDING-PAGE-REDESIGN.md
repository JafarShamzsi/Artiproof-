# ArtiProof Landing Page — Complete Redesign Prompt

> **Use every skill you have installed.** Before writing any code, run your skills to understand the design system, audit the current state, and inform your decisions. Specifically:
>
> 1. **Read `PRODUCT.md` and `DESIGN.md`** at the project root — these are your design bible. Every decision must align with them.
> 2. **Run `/impeccable document`** to extract the current visual system from the codebase and verify your changes won't break existing conventions.
> 3. **Run `/impeccable teach`** if you haven't already — learn the brand personality and anti-patterns.
> 4. **Use the taste-skill** for component-level quality — check that every component you write or rewrite passes its design standards for typography, spacing, and color.
> 5. **Use Emil Kowalski's skill** for all animations and micro-interactions — spring physics, scroll-driven motion, hover states, and transitions should follow his principles.
> 6. **Use the Anthropic frontend-design skill** if installed — make bold, distinctive choices. ArtiProof is NOT generic dark SaaS.
> 7. **Use Vercel web-design-guidelines** if installed — audit every component for accessibility, ARIA, focus states, and semantic HTML.
>
> **DO NOT STOP until every section listed below is complete, polished, and verified.** Run `/impeccable polish` on each section after implementing it. Run `/impeccable audit` at the end on the full page.

---

## Context

**Product:** ArtiProof — a 5-in-1 research integrity platform (AI detection, plagiarism, citation rings, fact-checking, researcher scoring).

**Target users:** PhD candidates, researchers, university administrators, and institutional buyers in Azerbaijan and the Eastern Partnership (EaP) region. They arrive skeptical — they've seen Turnitin and GPTZero. The landing page must earn trust through evidence, not hype.

**Brand personality:** Calm authority. Specific over loud. Rigorous, transparent, regional. Emerald carries every primary action; everywhere else is tinted neutral. The brand color should appear < 12% of the visible surface.

**Anti-patterns (MUST AVOID):**
- NO gradient text (`background-clip: text` on headlines)
- NO glassmorphism cards stacked inside other cards
- NO identical icon-grid feature sections (icon + title + 3 lines × 6)
- NO side-stripe accent borders > 1px
- NO hero-metric template (big number / small label / gradient accent)
- NO animated particles, falling stars, or decorative motion
- NO "AI-powered" or "blazing-fast" copy
- NO stock photos of diverse students smiling at laptops
- NO bounce or elastic easing — use cubic-bezier `[0.16, 1, 0.3, 1]` (out-expo)

**What this SHOULD feel like:** Linear meets a Nature methods paper. Clean, confident, evidence-based. Every section either presents proof or earns the skeptic's next 200 pixels of scroll.

---

## Technical Stack

- **Framework:** Next.js 14+ (App Router), React 19
- **Styling:** Tailwind CSS 4
- **Animation:** Framer Motion (already installed)
- **Fonts:** Plus Jakarta Sans (display, `font-display`), Inter (body, `font-sans`), Geist Mono (`font-mono`)
- **Components:** shadcn/ui base + custom components in `components/ui/`
- **Icons:** lucide-react
- **Design tokens:** `frontend/src/lib/design-tokens.ts`
- **Color source of truth:** `frontend/src/lib/colors.ts`
- **Existing files to modify:** All in `frontend/src/components/landing/`

---

## File Structure

```
frontend/src/
├── app/(landing)/
│   └── page.tsx                    ← Landing page composition
├── components/landing/
│   ├── Navbar.tsx                  ← Sticky nav with CTA
│   ├── HeroSection.tsx             ← Outcome headline + product mockup
│   ├── ScannerPreview.tsx          ← Interactive "try it" demo
│   ├── TrustSection.tsx            ← Logo strip + sourced stats
│   ├── ComparisonSection.tsx       ← Feature comparison vs competitors
│   ├── FeaturesSection.tsx         ← 5 integrity engines explained
│   ├── PricingSection.tsx          ← 3 tiers + mini-FAQ
│   ├── CTASection.tsx              ← Final conversion section
│   ├── Footer.tsx                  ← Links + legal
│   ├── SmoothScrollProvider.tsx    ← Smooth scroll wrapper
│   └── shared/
│       └── ScrollReveal.tsx        ← Viewport-triggered animation
├── components/ui/
│   ├── button.tsx                  ← Button variants
│   ├── fade-in.tsx                 ← FadeIn animation wrapper
│   ├── score-gauge.tsx             ← SVG radial score meter
│   ├── empty-state.tsx             ← Empty state component
│   └── breadcrumb.tsx              ← Navigation breadcrumbs
├── lib/
│   ├── design-tokens.ts            ← Color, spacing, typography, motion tokens
│   └── colors.ts                   ← Score/verdict color functions
└── app/
    ├── layout.tsx                  ← Root layout (fonts, metadata)
    └── globals.css                 ← Global styles + cta-glow
```

---

## Section-by-Section Redesign Instructions

### 0. Background & Page Wrapper

**File:** `frontend/src/app/(landing)/page.tsx`

The current background is a single subtle emerald glow blob. This is fine and respects the DESIGN.md constraints. Do NOT add grid patterns, multiple gradient blobs, or animated particles.

**Enhance:**
- Add a very subtle noise texture overlay (CSS-only, no image) at 2-3% opacity for depth
- Ensure the gradient glow responds slightly to scroll position (parallax at 0.1x rate) using Framer Motion's `useScroll` — but ONLY if `prefers-reduced-motion` is not set
- Section dividers already use gradient hairlines — keep them

```css
/* Noise texture - add to globals.css */
.noise::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: -5;
  opacity: 0.025;
  pointer-events: none;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E");
}
```

---

### 1. Navbar — `Navbar.tsx`

**Current state:** Has ArtiProof logo, nav links, and CTA button.

**Redesign goals:**
- The navbar should feel like it disappears until needed. Use `backdrop-blur-xl` and `bg-zinc-950/80` (already done — verify).
- On scroll down, the navbar should smoothly slide up and hide. On scroll up, it should slide back down. Use Framer Motion's `useMotionValueEvent` with `useScroll`.
- The "Get Started Free" CTA button should have a subtle emerald glow on hover (not the full `cta-glow` — that's reserved for hero).
- Add smooth scroll behavior for anchor links (#pricing, #features, etc.).
- On mobile, the hamburger menu should animate with a staggered reveal of menu items.
- Active section indicator: as the user scrolls, highlight the nav link corresponding to the current section using `IntersectionObserver`.

**Animation details (use Emil Kowalski principles):**
- Hide/show transition: `translateY(-100%)` with 300ms out-expo easing
- Mobile menu items: stagger 50ms each, fade + slide from right (12px)
- Active indicator: a small dot or underline that slides to the active link position using `layoutId` (Framer Motion shared layout animation)

---

### 2. Hero Section — `HeroSection.tsx`

**Current state:** Already has outcome-driven headline, product mockup, single CTA, trust badge. This is good.

**Redesign goals — take it to the next level:**

**a) Headline animation upgrade:**
- Instead of a simple fade-up, use a word-by-word reveal where each word slides up from a masked container. Think Linear's hero text animation.
- The emerald-highlighted "trust the research" should have a subtle underline that draws in from left to right after the text appears (SVG path animation, 600ms).
- Use `overflow-hidden` on each word container for the mask effect.

```typescript
// Word-by-word reveal pattern:
const words = "Know if you can trust the research.".split(" ");

{words.map((word, i) => (
  <span key={i} className="inline-block overflow-hidden">
    <motion.span
      className="inline-block"
      initial={{ y: "100%" }}
      animate={{ y: 0 }}
      transition={{ 
        duration: 0.5, 
        delay: 0.1 + i * 0.05, 
        ease: [0.16, 1, 0.3, 1] 
      }}
    >
      {word === "trust" || word === "the" || word === "research." 
        ? <span className="text-emerald-400">{word}</span> 
        : word}
    </motion.span>
  </span>
))}
```

**b) Product mockup enhancements:**
- The browser chrome mockup is good. Add a subtle entrance animation where the mockup slides up + fades in while slightly scaling from 0.95 to 1.0.
- The claim rows inside the mockup should appear sequentially with a typewriter-like stagger (each row fades in 100ms after the previous).
- The AI bar should animate its width from 0% to 14% with a smooth easing after a 1.2s delay.
- The floating credibility badge should bounce in slightly (spring animation, stiffness 300, damping 25) from the bottom-left with a 1.5s delay.

**c) Ambient interaction:**
- When the user hovers over the product mockup, add a very subtle 3D tilt effect (max 3 degrees) using `perspective` and `rotateX`/`rotateY` based on mouse position. Use Framer Motion's `useMotionValue` and `useTransform`.
- On mobile, this should be disabled (no hover).

**d) Scroll indicator:**
- At the bottom of the hero viewport, add a subtle animated chevron or line that pulses to indicate "scroll down". This should fade out after the user scrolls 100px. Simple CSS animation, not Framer Motion.

---

### 3. Scanner Preview — `ScannerPreview.tsx`

**Current state:** Interactive demo where users can click example URLs to see mock results.

**Redesign goals:**
- This is the "try before you buy" section. It needs to feel alive and responsive.
- The input field should have a blinking cursor animation and show placeholder text that types itself ("Paste a URL, DOI, or text to check...") — use a typewriter effect with 40ms per character.
- When the user clicks an example URL, the transition to the results view should be cinematic:
  1. The URL text should highlight (emerald bg wash, 200ms)
  2. A progress bar appears and fills (fake, 1.5s with ease-in-out)
  3. The results card slides in from below with a slight blur-to-clear transition
- The results card should show a mini version of the actual check results (score, 3 claim verdicts, AI bar) matching the hero mockup style.
- Add a "Try with your own" button that links to `/register`.

**Animation details:**
- URL highlight: `bg-emerald-500/10` grows from the center outward using `scaleX` from 0 to 1
- Progress: linear fill with subtle shimmer overlay (CSS animation)
- Results entrance: `translateY(20px)` + `opacity: 0` → `translateY(0)` + `opacity: 1`, 400ms with out-expo
- Card background: `filter: blur(4px)` → `filter: blur(0)`, synced with opacity

---

### 4. Trust Section — `TrustSection.tsx`

**Current state:** Has institution names and 4 stats with source attributions.

**Redesign goals:**
- The stats should use count-up animations that trigger when the section enters the viewport. Use a custom hook with `useInView` from Framer Motion:

```typescript
function useCountUp(target: number, duration = 2000) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  
  useEffect(() => {
    if (!inView) return;
    const start = Date.now();
    const tick = () => {
      const elapsed = Date.now() - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      setCount(Math.floor(eased * target));
      if (progress < 1) requestAnimationFrame(tick);
    };
    tick();
  }, [inView, target, duration]);
  
  return { ref, count };
}
```

- For "14,000+", count up from 0 to 14000 with comma formatting
- For "92%", count from 0 to 92
- For "$392K", count from 0 to 392 and prepend "$" and append "K"
- For "< 2min", just fade in (no count-up for this one)

- The institution names should scroll horizontally in an infinite marquee if there are more than 5. Use CSS animation (`translateX(-50%)` loop on a duplicated list). Speed: 30s for one complete cycle. Pause on hover.
- Each stat card should have a subtle border glow that pulses once when it enters the viewport (emerald-500/10 shadow that fades in and out over 1.5s).

---

### 5. Comparison Section — `ComparisonSection.tsx`

**Current state:** Feature comparison table with checkmarks.

**Redesign goals:**
- The ArtiProof column should be visually distinguished — not just with a border, but with a subtle vertical gradient behind it (`bg-emerald-500/[0.03]` fading to transparent at top and bottom).
- Row hover effect: when hovering a row, the entire row gets a `bg-white/[0.02]` highlight with 150ms transition.
- The checkmarks in the ArtiProof column should be slightly larger and bolder than competitors' checkmarks.
- Features exclusive to ArtiProof (citation rings, researcher scoring, fact-checking) should have a small "Unique" badge in `text-emerald-400` next to the feature name.
- Entrance animation: the table should build row-by-row from top to bottom with 30ms stagger, each row sliding in from left (`translateX(-12px)` + fade).
- On mobile, transform the table into a card-based layout where each competitor is a separate card showing only checkmark counts ("ArtiProof: 8/8 features" vs "Turnitin: 3/8 features").

---

### 6. Features Section — `FeaturesSection.tsx`

**Current state:** 353 lines. Shows the 5 integrity engines.

**Redesign goals — THIS IS THE MOST IMPORTANT SECTION TO GET RIGHT:**

Do NOT use the generic icon-grid pattern (icon + heading + 3 lines × 5). Instead, use one of these approaches:

**Option A: Stacked showcase (recommended)**
Each feature gets its own full-width block. Left side: text (title + 2-sentence description + 1 key metric). Right side: a mini-visualization or mockup specific to that feature. Alternate left/right alignment for visual rhythm.

```
┌─────────────────────────────────────────────┐
│  [Text: AI Detection]      [Mini AI bar]    │
├─────────────────────────────────────────────┤
│  [Mini citation graph]   [Text: Citation    │
│                           Ring Detection]   │
├─────────────────────────────────────────────┤
│  [Text: Fact-Checking]   [Mini verdict      │
│                           cards]            │
└─────────────────────────────────────────────┘
```

**Option B: Tabbed showcase**
5 tabs across the top. Clicking each tab reveals a dedicated panel with a larger visualization + detailed description. The tab transition should crossfade with a slight slide (use Framer Motion `AnimatePresence`).

**For either option, each feature needs a unique mini-visualization:**

1. **AI Detection** — An animated bar chart showing paragraph-by-paragraph AI probability. Bars should grow upward when the section enters viewport. Color: emerald for low, amber for medium, red for high.

2. **Plagiarism Detection** — A text block with highlighted matching phrases that animate in with a yellow/amber highlight sweep.

3. **Citation Ring Detection** — A mini force-directed graph (use SVG, NOT a library). 5-6 nodes with lines between them. Suspicious connections pulse red. Nodes should subtly float (2px sine wave, 3s period).

4. **Fact-Checking** — 3 mini verdict cards (True/False/Misleading) that flip in sequentially. Each shows a one-line claim with a verdict badge.

5. **Researcher Scoring** — A half-circle gauge that fills to 73 with the score number appearing. Below it, 3 small metric bars (h-index, self-citation rate, citation velocity).

**Animation timing for all visualizations:** Start when the section/tab enters viewport. Duration 1-2s. Use `useInView` from Framer Motion.

**Key metric per feature (use these real numbers):**
- AI Detection: "Analyzes up to 20 paragraphs per document"
- Plagiarism: "Cross-references 200M+ academic papers"
- Citation Rings: "Detects mutual-citation networks of 5+ papers"
- Fact-Checking: "Verifies claims against Google Fact Check API"
- Researcher Scoring: "Adjusts h-index for self-citation inflation"

---

### 7. Pricing Section — `PricingSection.tsx`

**Current state:** Already correct with $0 / $20 / Custom tiers, monthly/yearly toggle, mini-FAQ.

**Redesign goals — add polish:**
- The Pro card (Most Popular) should have a subtle animated border. Use a conic gradient that rotates:

```css
/* Rotating border gradient for Pro tier */
@property --angle {
  syntax: '<angle>';
  initial-value: 0deg;
  inherits: false;
}

.pro-border {
  background: conic-gradient(from var(--angle), #10b981, transparent, transparent, #10b981);
  animation: rotate-border 4s linear infinite;
  padding: 1px;
  border-radius: 0.75rem;
}

@keyframes rotate-border {
  to { --angle: 360deg; }
}
```

- But CHECK `@property` browser support first. Fallback to a static emerald border for unsupported browsers.
- The monthly/yearly toggle should animate the price change — old price fades up while new price fades in from below (crossfade with `AnimatePresence`).
- Feature list items should have a subtle stagger animation (30ms each) when the pricing section enters viewport.
- The "Most Popular" badge should have a subtle shimmer effect (a horizontal gradient highlight that slides across the text every 3s).

**Mini-FAQ:**
- Make the FAQ items expandable (click to expand answer, with height animation using `motion.div` with `layout`).
- Default: all collapsed except the first one.
- Collapse animation: 200ms out-expo.

---

### 8. CTA Section — `CTASection.tsx`

**Current state:** 31 lines. Basic final call-to-action.

**Redesign goals — make this the "close":**
- Headline: "Start checking research integrity in 90 seconds."
- Subline: "Free for your first 10 analyses. No credit card, no commitment."
- Single CTA button with full `cta-glow` effect.
- Background: a subtle radial gradient centered behind the CTA, emerald-500 at 3% opacity, expanding to transparent. This creates a "spotlight" effect.
- Below the CTA, add a small trust line: "Join researchers at [3 university names] already using ArtiProof."
- The entire section should be wrapped in a subtle border card (`border-zinc-800 rounded-2xl bg-zinc-900/30 p-12`).
- On viewport enter, the CTA button should scale from 0.9 to 1.0 with a spring animation.

---

### 9. Footer — `Footer.tsx`

**Current state:** 101 lines.

**Redesign goals:**
- 3-column layout: Product, Company, Resources — with only real, working links.
- Left side: ArtiProof logo + one-liner tagline + social links (GitHub if applicable).
- Bottom bar: "© 2026 ArtiProof. All rights reserved." + "Privacy" + "Terms" links.
- The footer should feel grounded — slightly lighter background (`bg-zinc-900/50` vs the page's `bg-zinc-950`).
- No animations in the footer. Keep it static and fast.
- Remove ANY dead # links. If a page doesn't exist, either create a placeholder or don't link it.

---

## Global Animation Principles

Follow these rules for ALL animations on the page:

1. **Duration:** 300-500ms for entrance animations. 150ms for hover/interaction states.
2. **Easing:** Always `[0.16, 1, 0.3, 1]` (out-expo). Never `ease-in`, never bounce, never elastic.
3. **Direction:** Elements enter from below (12-24px `translateY`) or from their natural position (scale 0.95→1.0). Never from above or from the sides (except for specific effects like the comparison table rows).
4. **Stagger:** 30-50ms between siblings. Never more than 100ms.
5. **Viewport trigger:** All scroll-driven animations use `viewport: { once: true, margin: "-100px" }`. Animations play once, never replay.
6. **Reduced motion:** EVERY animation must check `prefers-reduced-motion`. When set, animations complete instantly (duration: 0, no transforms).
7. **No layout shift:** Never animate `width`, `height`, or `margin` on elements that affect document flow. Use `transform` and `opacity` only.
8. **Performance:** Use `will-change: transform` on elements that animate. Remove it after animation completes.

---

## Color Rules

1. **Emerald appears ONLY on:** Primary CTA buttons, the "ArtiProof" column in comparison, score/verdict emerald states, the logo, and the "Most Popular" badge. Nowhere else.
2. **Text hierarchy:** Headings = `text-white`. Body = `text-zinc-400`. Captions/sources = `text-zinc-500`. Disabled/excluded = `text-zinc-600`.
3. **Borders:** Default = `border-zinc-800`. Hover = `border-zinc-700`. Active/selected = `border-emerald-500/40`.
4. **Backgrounds:** Page = `bg-zinc-950`. Cards = `bg-zinc-900/40`. Elevated = `bg-zinc-900/80 backdrop-blur-xl`.
5. **Never use:** Gradient text, colored shadows on non-CTA elements, or more than 2 non-neutral colors in any single section.

---

## Typography Rules

1. **Headlines:** `font-display` (Plus Jakarta Sans), `font-bold`, `tracking-tight`, `text-balance`.
2. **Body:** `font-sans` (Inter), `text-sm` or `text-base`, `text-zinc-400`.
3. **Eyebrows/labels:** `text-xs font-medium uppercase tracking-wider text-emerald-400` (brand) or `text-zinc-500` (neutral).
4. **Numbers/scores:** `font-display tabular-nums` for consistent alignment.
5. **Mono:** Only for ORCIDs, DOIs, code snippets, and technical IDs.

---

## Responsive Breakpoints

- **Mobile (< 640px):** Single column everything. Hero text 4xl. Features stacked vertically. Comparison as cards. Pricing stacked.
- **Tablet (640-1024px):** 2-column grid where applicable. Hero stays 2-col on lg+.
- **Desktop (1024px+):** Full layouts as designed.

---

## Final Checklist — DO NOT SKIP

After implementing everything above:

1. **Run `/impeccable polish` on every landing section** — let it suggest micro-improvements.
2. **Run `/impeccable audit` on the full landing page** — check for accessibility, contrast, spacing issues.
3. **Run the taste-skill audit** — verify component quality meets its standards.
4. **Check accessibility:**
   - Tab through the entire page — every interactive element must have visible focus styling
   - All images/icons have `aria-hidden="true"` or `alt` text
   - All animations respect `prefers-reduced-motion`
   - Color contrast meets WCAG 2.1 AA (4.5:1 for body text, 3:1 for large text)
   - Skip-to-content link works
5. **Check performance:**
   - No layout shifts during animations
   - Lazy-load everything below the fold
   - Total JS bundle for landing page < 200KB gzipped
   - No render-blocking CSS
6. **Check mobile:**
   - Test at 375px width (iPhone SE)
   - Test at 390px width (iPhone 14)
   - All text readable without horizontal scroll
   - Touch targets ≥ 44px
7. **Visual verification:**
   - Take a screenshot of the full landing page
   - Compare against the DESIGN.md anti-patterns — none should be present
   - Verify emerald < 12% of visible surface
   - Verify no section uses the same layout pattern as another
8. **Build passes:** `npm run build` completes with zero errors and zero warnings.

---

## Skills Installation Commands

If any of these skills are not installed, install them before starting:

```bash
# Core design skills
npx skills add Leonxlnx/taste-skill
npx skills add pbakaus/impeccable
npx skills add emilkowalski/skill

# Recommended additional skills
npx skills add https://github.com/anthropics/skills --skill frontend-design
npx skills add https://github.com/vercel-labs/agent-skills --skill web-design-guidelines
npx skills add https://github.com/vercel-labs/agent-skills --skill composition-patterns
```

**After installing, read each skill's SKILL.md to understand its rules before writing code.**

---

## Summary: What "Done" Looks Like

The landing page should feel like a product built by a well-funded YC startup — not a hackathon project. Every section earns the next scroll. Animations are purposeful, not decorative. Colors are restrained. Typography has clear hierarchy. Social proof is evidence-based. The overall impression should be: "these people take research seriously."

**Reference products for the vibe:**
- [Linear](https://linear.app) — for restraint, typography, and motion quality
- [Vercel](https://vercel.com) — for dark theme execution and section transitions
- [Resend](https://resend.com) — for clean developer-facing dark SaaS
- [Originality.ai](https://originality.ai) — for trust signals and evidence-heavy design in the same market

**DO NOT stop until the build passes, every section is polished, and the audit commands return clean results.**
