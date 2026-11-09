# ArtiProof Design Audit Report
## Full Brand, Landing Page & Product UI Analysis

**Date:** May 2, 2026  
**Scope:** Brand identity, landing page, dashboard/product UI, design system  
**Benchmark:** Y Combinator startups, Linear, Originality.ai, GPTZero, iThenticate, top dark-theme SaaS

---

## Executive Summary

ArtiProof has a solid technical foundation but its design sits at "developer prototype" level — functional but not investor-ready. The gap between ArtiProof and benchmark products like Linear, Originality.ai, or GPTZero is primarily in **visual polish, trust signals, content hierarchy, and brand system consistency** — not in layout or feature completeness. This report identifies 47 specific design gaps organized by severity.

---

## Part 1: Competitor & Market Analysis

### How Top Competitors Position Themselves

| Product | Theme | Hero Strategy | Trust Signals | Color System |
|---------|-------|---------------|---------------|--------------|
| **GPTZero** | Light/minimal | "AI detector made to preserve what's human" + inline demo | 99% accuracy badge, 17M users, 1M educators, NYT/BBC/Forbes logos | Blue accents on white, generous whitespace |
| **Originality.ai** | Dark/black | "Most Accurate AI Detector" + direct Google Docs CTA | Stanford/Harvard logos, 40+ institution badges, CNN/Nature press, accuracy tables | Black bg, white text, minimal accent |
| **iThenticate** | Light/premium | "Publish with confidence" + segmented pricing | Turnitin parent brand, institutional tiers, $125-300 transparent pricing | Deep teal/petrol, academic feel |
| **Copyleaks** | Light/corporate | Enterprise-first positioning | SOC-2, GDPR badges, LMS integrations | Blue/corporate, data-heavy |
| **Linear** | Dark/minimal | Product-as-hero, outcome-driven | Used by top startups, minimal but precise | Near-black + desaturated blue, OKLCH color space |

### Key Takeaways from YC Landing Page Formula

Based on analysis of 50+ YC startup pages:

1. **Hero = Outcome + Proof + Action.** Not "what we do" but "what you get." Single CTA, never competing buttons.
2. **Social proof within 1 scroll.** Logo strip of 6-10 recognizable brands near the hero, not buried in footer.
3. **3-step "How It Works."** Maximum 3 steps, visual not textual. ArtiProof already has this — good.
4. **Pricing with risk reducer.** "No credit card required" or "Free forever" adjacent to CTA. Middle tier highlighted.
5. **Mini-FAQ beside pricing.** Not at page bottom. Handles objections: security, integrations, time-to-value.
6. **< 2 second load time.** Compress media, lazy-load below fold.

### 2026 SaaS Design Trends ArtiProof Should Adopt

1. **Story-driven hero sections** — narrative headlines showing problem→solution arc (Notion, Linear, Framer)
2. **Immersive product previews** — interactive demos/video showing real workflows, not static screenshots
3. **Split-screen layouts** — text + visual in equal weight, especially for comparisons
4. **Real customer contexts** — actual interface screenshots over abstract illustrations
5. **Conversion-optimized nav** — persistent CTA in navbar, minimal links, action-focused labels
6. **Playful typography + confident color** — bold serif headlines, gradient overlays, emotional connection

---

## Part 2: Current ArtiProof Design Analysis

### A. Brand Identity

**What exists:**
- Shield icon (lucide-react) + "ArtiProof" wordmark in emerald-400
- Primary accent: emerald-400/500 (#10B981)
- Dark background: zinc-950 (#0a0a0a)
- Font: Inter (Google Fonts) — single weight system
- OKLCH color variables in globals.css (sophisticated but undocumented)

**What's missing:**

| Gap | Severity | Detail |
|-----|----------|--------|
| No brand guidelines document | HIGH | Colors, typography, logo usage rules undocumented |
| No secondary/accent palette | HIGH | Only emerald + zinc; needs a complementary color for warnings, info, highlights |
| No display/headline font | MEDIUM | Inter for everything = flat hierarchy; competitors use display fonts for headlines |
| No logo variations | MEDIUM | Only shield icon + text; no standalone logomark, no favicon system |
| No illustration/visual style | HIGH | FallingStars animation feels generic; no defined visual language |
| No brand voice documentation | LOW | Tone varies between sections (academic vs. startup vs. corporate) |

### B. Landing Page Design

**Strengths:**
- Framer Motion animations with staggered word reveals — smooth, professional
- Responsive grid (grid-cols-1 lg:grid-cols-2) — solid
- Interactive hover button — creative micro-interaction
- Scanner preview with example URLs — good "try before you buy" pattern
- High-contrast mode support in CSS — accessibility win

**Gaps (27 issues):**

#### Hero Section (6 issues)
1. **No product screenshot/demo in hero** — Competitors show the actual product. ArtiProof shows an animated globe (decorative, not informative).
2. **Headline is descriptive, not outcome-driven** — "Research Integrity Platform" describes what it IS, not what it DOES for the user. Better: "Catch Fraud Before Publication" or "Know If You Can Trust the Research."
3. **Two competing CTAs** — "Start Free Analysis" + "Watch Demo" split attention. YC formula: one dominant CTA.
4. **No social proof near hero** — No logos, no user count, no press badges. GPTZero has "17M users" and NYT/BBC logos in hero.
5. **Stats bar below hero uses wrong numbers** — 70%, 30%, 10K+ are fabricated. Must use verified data (14K+ retractions, 92% student AI use, $392K per retraction).
6. **Subheading in text-xl text-zinc-400** — Too small, too gray. Needs to be larger and brighter for readability.

#### Social Proof (4 issues)
7. **Zero customer/institution logos** — No "Trusted by" section. This is the #1 conversion killer for B2B SaaS.
8. **Zero testimonials** — No quotes from researchers, faculty, or institutions.
9. **No press/media logos** — No "As seen in" bar.
10. **No accuracy/performance claims with evidence** — GPTZero shows "99% accuracy." Originality.ai has comparison tables.

#### Pricing Section (4 issues)
11. **Wrong price ($19 instead of $20)** — Already flagged in code audit.
12. **"Free" tier marked "Most Popular"** — Signals no one pays. Should be on Pro tier.
13. **No risk reducer language** — No "No credit card required" or "Cancel anytime" near CTA.
14. **No FAQ beside pricing** — Objections (security, accuracy, integrations) unanswered at decision point.

#### Content & Messaging (5 issues)
15. **"Free for researchers and institutions"** in features section — Contradicts freemium model with paid tiers.
16. **No competitor comparison table** — iThenticate and Originality.ai prominently compare against competitors.
17. **CTA section says "Free for academic researchers worldwide"** — Same contradiction as #15.
18. **No "Why ArtiProof" or differentiation section** — What makes it different from Turnitin, GPTZero, etc.?
19. **Audience tabs (Researchers/Faculty/PhD/Institutions) lack specific value props** — Generic descriptions, not outcome-focused.

#### Visual & Layout (5 issues)
20. **FallingStars animation feels amateur** — Decorative particles common on template sites. Professional SaaS uses purposeful motion.
21. **No visual hierarchy in spacing** — mt-6, mt-8, mt-12 used arbitrarily. No 8px grid system.
22. **Footer has 15+ dead # links** — Looks broken. Undermines trust.
23. **No dark/light gradient transitions between sections** — Sections feel flat. Linear and Vercel use subtle gradient dividers.
24. **Feature cards use generic SVG illustrations** — Should show actual product screenshots or interactive demos.

#### Technical (3 issues)
25. **Images unoptimized** — `unoptimized: true` in next.config disables Next.js image optimization.
26. **No lazy-loading for below-fold content** — Everything loads at once.
27. **No Open Graph / social sharing meta tags** — Links shared on social media show no preview image.

### C. Dashboard / Product UI

**Strengths:**
- Collapsible sidebar with smooth transitions — professional
- VERDICT_CONFIG object with consistent color mapping — mature
- 4-column KPI grid on dashboard — clear data hierarchy
- Custom SVG trend charts — more control than chart libraries
- Sheet component for mobile navigation — responsive

**Gaps (12 issues):**

| # | Issue | Severity | Detail |
|---|-------|----------|--------|
| 28 | No empty states | HIGH | New users see blank tables. Should show onboarding prompt or illustration. |
| 29 | No loading skeletons | HIGH | Data loads with no visual feedback. Should use pulse/skeleton animations. |
| 30 | Score gauge is basic | MEDIUM | Just a number. Should be a radial gauge or meter with color gradient (like credit scores). |
| 31 | No breadcrumbs | MEDIUM | Deep pages (check/[id]) have no navigation context. |
| 32 | Results page is text-heavy | MEDIUM | Wall of data. Needs visual hierarchy — cards, collapsible sections, tabs. |
| 33 | Citation graph has no legend | MEDIUM | Colors used without explanation. |
| 34 | No data export options | LOW | Can't download report as PDF. |
| 35 | Button styles fragmented | MEDIUM | 3+ different button patterns, no shared Button component variants. |
| 36 | Spacing inconsistent | MEDIUM | Heading margins vary: mt-6, mt-8, mt-12 with no system. |
| 37 | Typography scale undefined | MEDIUM | 11+ text sizes used without hierarchy (text-xs through text-5xl). |
| 38 | No toast/notification system | LOW | Actions complete silently. Should confirm with toast. |
| 39 | Settings saved confirmation too brief | LOW | 2 seconds — users miss it. Should be 4+ seconds. |

### D. Design System & Consistency

**Gaps (8 issues):**

| # | Issue | Detail |
|---|-------|--------|
| 40 | No design tokens | Colors embedded in components, not abstracted as semantic tokens (e.g., `color-surface-primary`, `color-accent`) |
| 41 | No spacing scale | Should define 4px base: 4, 8, 12, 16, 24, 32, 48, 64, 96 |
| 42 | No type scale | Should limit to 6 sizes: caption (12), body (14), subtitle (16), title (20), h2 (24), h1 (32-40) |
| 43 | No component variants | Button, Card, Badge, Input need defined variants (primary/secondary/ghost/destructive) |
| 44 | Color opacity inconsistent | Mixing /10, /20, /50 without pattern. Need 3 defined opacity levels. |
| 45 | No icon size constraints | Icons used at various sizes per context with no scale. |
| 46 | No motion tokens | Animation durations and easings vary. Should define: fast (150ms), normal (300ms), slow (500ms). |
| 47 | Border strategy inconsistent | border-zinc-800 vs border-white/[0.06] — need one system. |

---

## Part 3: Priority Recommendations

### Tier 1: Do Before Demo/Pitch (Critical)

1. **Add real social proof** — Even 3 logos + 1 testimonial + user count transforms credibility
2. **Rewrite hero headline** — Outcome-driven, not descriptive
3. **Add product screenshot to hero** — Show the actual dashboard/results page
4. **Fix pricing** — $20 Pro, Custom Institution, risk reducer language
5. **Remove fake statistics** — Replace with verified data
6. **Kill dead footer links** — Either link to real pages or remove
7. **Remove "free for researchers" contradictions** — Align all messaging with freemium model

### Tier 2: Do Before Launch (High)

8. **Create brand guidelines** — Document colors, typography, spacing, voice
9. **Add display font for headlines** — Consider: Satoshi, Cabinet Grotto, Plus Jakarta Sans, or Outfit
10. **Build empty states** — Dashboard, check list, researcher list
11. **Add loading skeletons** — Every data-fetching page
12. **Upgrade score visualization** — Radial gauge with color gradient
13. **Add competitor comparison section** — "Why ArtiProof vs Turnitin/GPTZero"
14. **Replace FallingStars** — Use subtle gradient mesh or product-related motion

### Tier 3: Do Before Scale (Medium)

15. **Define design token system** — Semantic color names, spacing scale, type scale
16. **Extract component variants** — Button, Card, Badge, Input as reusable primitives
17. **Add section transitions** — Gradient dividers between landing page sections
18. **Build proper FAQ** — Beside pricing, handling security/accuracy/integration objections
19. **Add Open Graph meta tags** — Social sharing previews
20. **Enable image optimization** — Remove `unoptimized: true` flag

---

## Part 4: Benchmark Scorecard

| Dimension | ArtiProof Now | Target (Launch) | Best-in-Class |
|-----------|:---:|:---:|:---:|
| **Brand Identity** | 3/10 | 7/10 | Linear (9/10) |
| **Landing Page** | 4/10 | 7/10 | GPTZero (8/10) |
| **Social Proof** | 0/10 | 5/10 | Originality.ai (9/10) |
| **Product UI** | 6/10 | 8/10 | Linear (9/10) |
| **Design System** | 3/10 | 6/10 | Linear (10/10) |
| **Typography** | 4/10 | 7/10 | Vercel (9/10) |
| **Motion & Polish** | 5/10 | 7/10 | Framer (10/10) |
| **Accessibility** | 5/10 | 7/10 | — |
| **Mobile Responsive** | 5/10 | 7/10 | — |
| **Overall** | **3.9/10** | **6.8/10** | **~9/10** |

---

## Appendix: Design Reference Links

- [YC Landing Page Formula](https://www.thevccorner.com/p/win-the-first-5-seconds-the-yc-landing)
- [2026 SaaS Landing Page Trends](https://www.saasframe.io/blog/10-saas-landing-page-trends-for-2026-with-real-examples)
- [Dark SaaS Landing Pages Gallery](https://saaslandingpage.com/tag/dark/)
- [Linear Brand Guidelines](https://linear.app/brand)
- [Linear Design Philosophy](https://blog.logrocket.com/ux-design/linear-design/)
- [SaaS Brand Identity Examples](https://arounda.agency/blog/branding-examples)
- [B2B SaaS Color Palette Guide](https://www.kalungi.com/blog/choosing-branding-colors-for-your-b2b-saas-company)
- [SaaS Dashboard Design 2026](https://www.saasframe.io/blog/the-anatomy-of-high-performance-saas-dashboard-design-2026-trends-patterns)
- [SaaS Branding Guide](https://www.wunderdogs.co/thoughts-and-views/saas-brand-guidelines-the-complete-guide-to-building-a-brand-system-that-scales)
