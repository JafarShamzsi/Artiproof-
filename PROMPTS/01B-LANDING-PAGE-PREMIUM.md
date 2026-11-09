# CivicGuards — Premium Landing Page (Designer-Grade)

## Context
Read `00-PROJECT-BRIEF.md` for full project context. This prompt replaces the landing page section of Phase 1. This landing page will be reviewed by UX designers and must be portfolio-quality. Think: Palantir AIP meets Linear meets VirusTotal — dark, cinematic, data-rich, with 3D objects, scroll-driven animations, and micro-interactions everywhere.

## Design Philosophy
- **Dark cinematic** — near-black backgrounds (#09090b zinc-950) with glowing accent elements
- **Data-as-aesthetic** — the UI itself should feel like a threat intelligence dashboard
- **Motion is meaning** — every animation serves a purpose (reveal, emphasize, guide)
- **Glass morphism + glow** — frosted glass cards with subtle border glows
- **Typography-forward** — large, confident headings, tight spacing, system font stack or Inter/Geist
- **No stock photos** — only generated 3D visuals, abstract data art, and UI screenshots

---

## Tech Stack for Landing Page

```bash
# Core
npm install @react-three/fiber @react-three/drei three
npm install framer-motion
npm install gsap @gsap/react         # GSAP + ScrollTrigger for scroll animations
npm install lenis                     # Smooth scroll
npm install lucide-react

# Already installed from Phase 1
# next, tailwind, shadcn/ui, typescript
```

### Architecture:
```
src/
├── app/(landing)/
│   ├── page.tsx                    # Landing page (assembles all sections)
│   └── layout.tsx                  # Landing layout (no sidebar, has navbar + footer)
├── components/landing/
│   ├── Navbar.tsx                  # Sticky glassmorphism navbar
│   ├── HeroSection.tsx             # 3D globe + headline
│   ├── HeroScene.tsx               # React Three Fiber canvas (3D globe)
│   ├── ProblemSection.tsx          # Animated stats counter
│   ├── HowItWorksSection.tsx       # 3-step horizontal scroll
│   ├── ScannerPreview.tsx          # Interactive scanner demo
│   ├── EngineGrid.tsx              # VirusTotal-style engine grid
│   ├── FeaturesSection.tsx         # Bento grid feature cards
│   ├── AudienceSection.tsx         # User persona tabs
│   ├── DISARMSection.tsx           # DISARM matrix preview
│   ├── EducationSection.tsx        # Gamification preview
│   ├── PricingSection.tsx          # Pricing cards
│   ├── CTASection.tsx              # Final CTA + waitlist
│   ├── Footer.tsx                  # Footer
│   └── shared/
│       ├── GlowCard.tsx            # Reusable glassmorphism card with border glow
│       ├── AnimatedCounter.tsx     # Number counter animation
│       ├── SectionHeading.tsx      # Consistent section headings
│       ├── GradientText.tsx        # Gradient text effect
│       ├── ParticleField.tsx       # Background particle animation
│       ├── GridPattern.tsx         # Subtle grid background pattern
│       └── ScrollReveal.tsx        # Reusable scroll-triggered reveal wrapper
```

---

## Global Effects & Utilities

### Smooth Scroll (Lenis):
```tsx
// In layout.tsx or a provider:
// Initialize Lenis for buttery smooth scrolling
// Sync with GSAP ScrollTrigger for scroll-driven animations
```

### Grid Background Pattern:
```tsx
// Subtle dot grid or line grid that covers the entire page background
// Very low opacity (0.03-0.05), zinc-800 colored
// Creates depth without distraction
// Optional: grid lines glow slightly near the cursor (mouse-follow effect)
```

### Scroll-Triggered Reveals:
```tsx
// Reusable ScrollReveal component using framer-motion
// Elements fade in + slide up (y: 40 → 0, opacity: 0 → 1)
// Staggered children (0.1s delay between siblings)
// threshold: 0.2 (triggers when 20% visible)
// once: true (only animate in, don't animate out)
```

### GlowCard Component:
```tsx
// Glassmorphism card used throughout the landing page
// - Background: rgba(255,255,255,0.03) with backdrop-blur-xl
// - Border: 1px solid rgba(255,255,255,0.06)
// - On hover: border glows with accent color (emerald-500/20 or cyan-500/20)
// - Optional: mouse-position-tracking gradient glow on the border
//   (the border glow follows the cursor as it moves over the card)
// - Subtle box-shadow on hover
// - Smooth transition (300ms)
```

### GradientText Component:
```tsx
// Text with animated gradient fill
// bg-gradient-to-r from-emerald-400 via-cyan-400 to-blue-400
// bg-clip-text text-transparent
// Optional: slow animation cycling the gradient position
```

---

## Section-by-Section Specification

---

### 1. NAVBAR (Sticky, Glassmorphism)

**Behavior:**
- Fixed at top, z-50
- Transparent on page load, gains glassmorphism background (backdrop-blur-xl + bg-zinc-950/80) after scrolling past hero
- Transition between states: smooth 300ms

**Layout:**
- Left: Logo mark (shield icon from lucide-react or custom SVG) + "CivicGuards" in bold
- Center: Navigation links — Features, How It Works, Scanner, Education, Pricing
  - Each link has an underline hover effect (animated width from 0 to 100%)
  - Active section indicator (highlight current section based on scroll position)
- Right: "Sign In" (ghost button) + "Get Started" (primary button with gradient bg: emerald-500 to cyan-500)
- Mobile: hamburger icon → full-screen overlay menu with large links, animated entrance

**Visual:**
- Height: 64px desktop, 56px mobile
- Max-width container (1280px) centered
- Border-bottom: 1px solid rgba(255,255,255,0.06) when scrolled

---

### 2. HERO SECTION (3D Globe + Bold Statement)

**This is the most important section. It must be jaw-dropping.**

**Layout:**
- Full viewport height (100vh)
- Split: Left side (text, ~55%) + Right side (3D scene, ~45%)
- On mobile: stack vertically, text on top, 3D scene below (reduced size)

**Left Side — Text:**
- Eyebrow text (small, uppercase, tracking-wider, emerald-400): "MISINFORMATION THREAT INTELLIGENCE"
- Main headline (text-6xl md:text-7xl lg:text-8xl, font-bold, text-white, leading-tight):
  "The Truth Has<br/>a **Guardian**"
  - "Guardian" uses GradientText (emerald → cyan gradient)
  - Text animates in: each word staggers in from bottom (framer-motion, 0.05s delay per word)
- Subheadline (text-xl, text-zinc-400, max-w-lg, mt-6):
  "Multi-engine AI analysis. Real-time threat intelligence. The VirusTotal of misinformation — built for everyone."
  - Fades in after headline animation completes
- CTA buttons (mt-8, flex gap-4):
  - "Launch Scanner" — gradient bg (emerald-500 → cyan-500), white text, px-8 py-4, rounded-lg, hover: glow effect + slight scale up (1.02)
  - "See How It Works" — ghost/outline button, border-zinc-700, text-zinc-300, hover: border-zinc-500
  - Buttons fade+slide in after subheadline
- Social proof line (mt-12, text-sm, text-zinc-500):
  - "Trusted by researchers at" + small logos/text of organizations (placeholder: "MIT · Stanford · Reuters · BBC Verify")
  - Or: "Join 2,400+ people already on the waitlist"

**Right Side — 3D Scene (React Three Fiber):**

Build an interactive 3D globe/network visualization:

```tsx
// React Three Fiber Canvas with:
// 1. A wireframe globe (sphere geometry with visible edges/grid lines)
//    - Color: emerald-500 with low opacity wireframe
//    - Slowly auto-rotating (y-axis, 0.001 rad/frame)
//    - Slight tilt (23.5° like Earth)
//
// 2. Glowing nodes scattered on the globe surface (50-80 nodes)
//    - Small spheres (radius 0.02) with emissive emerald/cyan glow
//    - Randomly distributed on the sphere surface
//    - Pulse animation (scale oscillates between 0.8 and 1.2, random phase)
//
// 3. Arc connections between nodes (20-30 arcs)
//    - Curved lines connecting pairs of nodes
//    - Color: gradient from emerald-500 to cyan-500
//    - Animated: lines "draw" themselves (growing from one node to another)
//    - New arcs appear every 2-3 seconds, old ones fade out
//    - Represents the "spread of misinformation" visually
//
// 4. Floating particles around the globe (200+ tiny particles)
//    - Tiny dots orbiting loosely around the globe
//    - Very low opacity, creates atmosphere
//    - drift slowly in random directions
//
// 5. Mouse interaction:
//    - Globe slightly follows mouse position (subtle, ±5° rotation)
//    - On hover over a node: node grows + shows a tiny tooltip ("Claim detected")
//
// 6. Post-processing:
//    - Bloom effect (subtle, intensity 0.3) to make glowing elements pop
//    - Vignette effect (subtle darkening at edges)
//
// Libraries:
// - @react-three/fiber for the canvas
// - @react-three/drei for OrbitControls (disabled user control, just auto-rotate),
//   Float, MeshDistortMaterial, Bloom via @react-three/postprocessing
// - three for geometries
```

**Performance:**
- Use `<Suspense>` with a loading fallback
- Limit to 60fps, use `frameloop="demand"` if needed
- On mobile: render a simpler version (fewer particles, no post-processing)
- Detect low-power devices and show a static fallback image

**Scroll Behavior:**
- As user scrolls down past hero, the globe slowly zooms out and fades
- Parallax: text moves up faster than the 3D scene

---

### 3. SOCIAL PROOF / STATS BAR (Scroll-Triggered Counters)

**Layout:**
- Narrow section, full-width dark card (bg-zinc-900/50 with border-y border-zinc-800)
- 4 stats in a row (grid-cols-4 on desktop, grid-cols-2 on mobile)

**Stats (animated counters — numbers count up when scrolled into view):**
- "68%" — "of adults encounter misinformation weekly"
- "900%" — "increase in deepfakes since 2020"
- "$78B" — "economic impact of misinformation annually"
- "< 3sec" — "average time to share without reading"

**Animation:**
- Each number counts up from 0 to final value over 2 seconds
- Easing: easeOut
- Staggered start (0.2s between each)
- Only triggers once when section enters viewport

---

### 4. HOW IT WORKS (3-Step Horizontal Scroll or Sticky Scroll)

**Concept:** As the user scrolls, each step reveals with a sticky left panel + content transitioning on the right. Similar to how Linear or Stripe present features with scroll-pinned sections.

**Layout Option — Sticky Scroll:**
- Left side (40%, sticky): Large step number (outlined, text-9xl, gradient stroke) + step title
- Right side (60%): Content card that transitions between steps as user scrolls
- Total scroll distance: 3x viewport height (one vh per step)

**Steps:**

**Step 1: "Submit"**
- Icon: Upload icon (lucide)
- Title: "Paste. Upload. Scan."
- Description: "Submit any claim, URL, screenshot, or social media post. Our system handles text, images, and links."
- Visual: Animated mockup of the scan input UI — show a URL being typed into the input field with a blinking cursor, then the "Analyze" button glowing

**Step 2: "Analyze"**
- Icon: Brain/CPU icon
- Title: "6 Engines. Zero Bias."
- Description: "Multiple AI engines analyze simultaneously — cross-referencing fact-check databases, scoring source credibility, and classifying tactics using the DISARM framework."
- Visual: EngineGrid component (see section 5 below) with engines lighting up one by one in sequence

**Step 3: "Results"**
- Icon: Shield check icon
- Title: "Threat Report. Instantly."
- Description: "Get a comprehensive threat score, engine-by-engine breakdown, DISARM classification, and actionable intelligence — all in seconds."
- Visual: Mock scan results card showing a threat score gauge, verdict badges, and DISARM tags

**Transition Animation:**
- Steps crossfade as the user scrolls
- Step number morphs (1 → 2 → 3) with a smooth scale + position animation
- Progress indicator: three dots on the side showing current step

---

### 5. SCANNER DEMO (Interactive Preview)

**This is the "wow" moment — let visitors try a mini version of the scanner.**

**Layout:**
- Section heading: "See It In Action" with GradientText
- Centered, max-w-4xl

**Interactive Demo:**
- A functioning input field where the visitor can paste a claim or pick from pre-loaded examples
- Pre-loaded example buttons below the input: "Try: 'COVID vaccines contain microchips'" / "Try: '5G towers cause cancer'" / "Try: 'Election was stolen'"
- When clicked/submitted:
  1. Input field shows the text
  2. Animate: "Scanning..." progress bar
  3. Engine cards light up one by one (0.5s between each) with staggered animation
  4. Each engine shows a verdict (use pre-computed mock data for the examples)
  5. Threat score gauge animates from 0 to final value
  6. DISARM technique tags appear

**Engine Grid (VirusTotal-style):**
```
┌─────────────────┬──────────────────┬──────────────────┐
│  🔴 Grok AI     │  🔴 Gemini AI    │  🟡 Fact Check DB│
│  FALSE (0.92)   │  FALSE (0.88)    │  DISPUTED (0.76) │
├─────────────────┼──────────────────┼──────────────────┤
│  🟢 Internal DB │  🔴 Source Cred  │  🔴 DISARM       │
│  KNOWN (0.95)   │  LOW CRED (0.84) │  T0023,T0049     │
└─────────────────┴──────────────────┴──────────────────┘
```

- Each engine card is a GlowCard
- Verdict colors: green = safe, yellow = suspicious, orange = misleading, red = false
- Confidence score as a small progress bar
- The grid should feel alive — subtle pulse animations on the status indicators

**Below the demo:**
- "This is a preview. Sign up for full analysis with detailed reports." + CTA button

---

### 6. FEATURES — BENTO GRID

**Layout:** Asymmetric bento grid (like Apple's feature grids or Linear's homepage).

**Grid structure (desktop):**
```
┌────────────────────────┬──────────────┐
│                        │              │
│   SCANNER (large)      │  EDUCATION   │
│   2 cols, 2 rows       │  1 col       │
│                        │  1 row       │
├───────────┬────────────┼──────────────┤
│           │            │              │
│  THREAT   │  COMMUNITY │  DISARM      │
│  FEED     │            │  FRAMEWORK   │
│  1 col    │  1 col     │  1 col       │
├───────────┴────────────┴──────────────┤
│                                       │
│  API ACCESS (full width, shorter)     │
│  3 cols, 1 row                        │
└───────────────────────────────────────┘
```

**Each Bento Card:**
- GlowCard with mouse-tracking border glow
- Icon (top-left, lucide, 24px, zinc-400)
- Title (text-lg, font-semibold, white)
- Description (text-sm, zinc-400, 2-3 lines)
- Visual element unique to each card:
  - **Scanner card (large)**: Animated mini threat gauge + floating verdict badges
  - **Education card**: Progress bar animation + badge icons + "Level 5" badge
  - **Threat Feed card**: Mini sparkline chart showing "trending threats" + pulsing red dot
  - **Community card**: Overlapping avatar circles + vote count animation
  - **DISARM card**: Mini matrix grid with cells coloring in sequence (like a heatmap building)
  - **API card**: Code snippet with syntax highlighting showing a cURL request + JSON response, typing animation

**Scroll Animation:**
- Cards stagger in as the section scrolls into view
- Each card has a slight delay (masonry reveal effect)

---

### 7. AUDIENCE SECTION (Who It's For)

**Layout:**
- Section heading: "Built for Truth-Seekers"
- Tab interface (shadcn Tabs or custom animated tabs)
- 5 tabs: Citizens | Journalists | Researchers | Educators | Organizations

**Each Tab Content:**
- Left: Description text + 3 bullet points of how they'd use CivicGuards + CTA
- Right: Stylized screenshot/mockup of their specific dashboard view
- Transition: tabs crossfade with a subtle slide

**Tab styling:**
- Horizontal tab bar with pill-style active indicator
- Active tab: gradient background (emerald → cyan), white text
- Inactive: transparent, zinc-400 text, hover: zinc-300
- Active indicator slides smoothly between tabs (framer-motion layout animation)

---

### 8. DISARM FRAMEWORK PREVIEW

**Layout:**
- Section heading: "Powered by DISARM" + subheading: "The MITRE ATT&CK of misinformation — now in your hands"
- Interactive mini-matrix

**Visual:**
- A simplified DISARM matrix (4 phases × 4 tactics = 16 cells)
- Cells are small colored squares in a grid
- Cells glow/pulse in sequence (like a heatmap animation)
- On hover: cell expands slightly, shows technique name
- Color intensity represents detection frequency
- Below the matrix: "CivicGuards classifies every threat using 200+ DISARM techniques"
- CTA: "Explore the full DISARM Matrix →"

**Animation:**
- When section enters viewport, cells fill with color in a wave pattern (left to right, top to bottom)
- Creates a satisfying "data loading" visual effect

---

### 9. EDUCATION PREVIEW (Gamification Showcase)

**Layout:**
- Section heading: "Level Up Your Immunity"
- Split: Left (mockup) + Right (text + gamification elements)

**Left Side — Mockup:**
- Stylized phone/browser frame showing a quiz question
- The quiz question animates: question text types in, then options slide in one by one
- One option gets selected (green glow), then "Correct! +20 XP" appears with a confetti burst

**Right Side:**
- Description text about the education system
- Gamification showcase:
  - Streak counter: fire emoji + "7 Day Streak" with flame animation
  - XP bar: animated progress bar filling up
  - Badge grid: 6 badges (3 earned/colored, 3 locked/grayscale) with hover tooltips
  - Mini leaderboard: 3 rows showing rank, name, XP

**Animation:**
- Elements cascade in from right as user scrolls
- XP bar fills up when visible
- Badge icons do a subtle bounce when they appear

---

### 10. PRICING SECTION

**Layout:**
- Section heading: "Choose Your Shield" (GradientText)
- 3 cards side by side (center card slightly elevated and larger — the "recommended" plan)

**Card Design:**
- **Free card**: bg-zinc-900, border-zinc-800. Simple and clean.
- **Pro card** (recommended): bg-gradient border (emerald-500/20 to cyan-500/20), slightly larger, "Most Popular" badge on top with gradient bg, subtle glow effect around the card
- **Enterprise card**: bg-zinc-900, border-zinc-800, "Contact Us" instead of price

**Each Card Contains:**
- Plan name
- Price (large text for Pro: "$12" + "/mo" smaller, or "$99/yr" toggle)
- Monthly/Yearly toggle (shared across all cards, saves 30%)
- Feature list with check icons (emerald-500 for included, zinc-600 for excluded)
- CTA button (Pro card: gradient bg, others: outline)

**Features List for Each Tier:**
```
FREE:
✓ 10 scans per day
✓ Basic threat score
✓ Education hub access
✓ Community participation
✗ Detailed engine results
✗ DISARM classification
✗ Export reports
✗ Bulk scanning
✗ Custom alerts
✗ API access

PRO ($12/mo):
✓ Unlimited scans
✓ Full engine-by-engine results
✓ Detailed DISARM classification
✓ Analytics dashboard
✓ Export PDF & CSV reports
✓ Bulk scanning (100/batch)
✓ Custom alerts (10)
✓ Priority processing
✗ API access
✗ Team management
✗ White-label

ENTERPRISE (Custom):
✓ Everything in Pro
✓ Unlimited bulk scanning
✓ API access
✓ Team management (50 seats)
✓ Webhook integrations
✓ White-label reports
✓ Dedicated support
✓ Custom SLA
```

**Animation:**
- Cards stagger in (center first, then sides)
- Hover: card lifts slightly (translateY -4px) with enhanced glow

---

### 11. TESTIMONIALS / TRUST (Optional — can use placeholder quotes)

**Layout:**
- Horizontal auto-scrolling carousel (infinite loop, pauses on hover)
- Cards with quote, name, role, small avatar (placeholder)
- Subtle: not the hero of the page, but adds social proof

---

### 12. FINAL CTA + WAITLIST

**Layout:**
- Full-width section with radial gradient background (dark center → zinc-950 edges)
- Centered content:
  - Headline (text-4xl, bold): "Join the Fight Against Misinformation"
  - Subtext: "Get early access to the most advanced misinformation intelligence platform."
  - Email input + "Join Waitlist" button (inline, like a search bar)
  - Below: "Join 2,400+ truth-seekers already on the list" + small avatar stack
- Background: Subtle particle animation (ParticleField component — floating dots)

**Email submission:**
- Validates email format
- Stores in database (new `waitlist` table: id, email, created_at)
- Shows success state: "You're in! We'll notify you when we launch."
- Error handling for duplicate emails: "You're already on the list!"

---

### 13. FOOTER

**Layout:**
- Dark (bg-zinc-950), border-top border-zinc-800
- 4 columns:
  - **CivicGuards**: Logo + tagline ("Defending truth with intelligence") + social icons (Twitter/X, GitHub, LinkedIn, Discord — placeholder links)
  - **Product**: Scanner, Education Hub, Threat Feed, API, Browser Extension, Pricing
  - **Company**: About, Blog, Careers, Press Kit, Contact
  - **Legal**: Privacy Policy, Terms of Service, Cookie Policy, Security
- Bottom bar: "© 2026 CivicGuards. All rights reserved." + "Built to defend truth."

**Style:**
- Links: text-zinc-500, hover: text-zinc-300, transition
- Compact, not too tall
- Social icons: 20px, zinc-500, hover: white

---

## Performance Requirements

- **Lighthouse score target**: 90+ Performance, 95+ Accessibility
- **First Contentful Paint**: < 1.5s
- **Largest Contentful Paint**: < 2.5s
- **3D scene**: Lazy-load the Three.js canvas. Use `<Suspense>` with a gradient placeholder.
- **Images**: Use Next.js `<Image>` with priority for above-fold, lazy for below
- **Fonts**: Use `next/font` with Inter or Geist font, preloaded
- **Bundle**: Dynamic import the 3D components (`next/dynamic` with `ssr: false`)
- **Reduced motion**: Respect `prefers-reduced-motion` — disable 3D, disable scroll animations, show static alternatives
- **Mobile**: Simpler 3D scene (or static image fallback), smaller animations, touch-friendly targets

---

## Color System

```css
/* Primary Palette */
--bg-primary: #09090b;        /* zinc-950 — main background */
--bg-secondary: #18181b;      /* zinc-900 — card backgrounds */
--bg-elevated: #27272a;       /* zinc-800 — elevated surfaces */
--border: rgba(255,255,255,0.06);  /* subtle borders */
--border-hover: rgba(255,255,255,0.12);

/* Text */
--text-primary: #fafafa;      /* zinc-50 — headings */
--text-secondary: #a1a1aa;    /* zinc-400 — body text */
--text-tertiary: #71717a;     /* zinc-500 — muted text */

/* Accent Gradient */
--accent-start: #10b981;      /* emerald-500 */
--accent-mid: #06b6d4;        /* cyan-500 */
--accent-end: #3b82f6;        /* blue-500 */

/* Verdict Colors */
--safe: #22c55e;              /* green-500 */
--suspicious: #eab308;        /* yellow-500 */
--misleading: #f97316;        /* orange-500 */
--false: #ef4444;             /* red-500 */

/* Glassmorphism */
--glass-bg: rgba(255,255,255,0.03);
--glass-border: rgba(255,255,255,0.06);
--glass-blur: 20px;
```

---

## Typography Scale

```css
/* Use Inter or Geist via next/font */
--font-display: text-8xl (96px) — Hero headline only
--font-h1: text-5xl (48px) — Section headings
--font-h2: text-3xl (30px) — Sub-section headings
--font-h3: text-xl (20px) — Card titles
--font-body: text-base (16px) — Body text
--font-small: text-sm (14px) — Captions, labels
--font-eyebrow: text-xs (12px) uppercase tracking-[0.2em] — Section labels
```

---

## Responsive Breakpoints

- **Mobile** (<640px): Single column, simplified 3D (or no 3D), stacked layout, reduced animations
- **Tablet** (640-1024px): Two-column where appropriate, smaller 3D scene
- **Desktop** (1024-1280px): Full layout, all animations
- **Wide** (1280px+): Max-width container, centered, generous spacing

---

## Deliverables Checklist
- [ ] Smooth scroll with Lenis
- [ ] Navbar with glassmorphism + scroll state change
- [ ] Hero with 3D globe (React Three Fiber) + word-by-word text animation
- [ ] Stats bar with animated counters
- [ ] How It Works with sticky scroll transitions
- [ ] Interactive scanner demo with pre-loaded examples
- [ ] Bento grid features with mouse-tracking glow cards
- [ ] Audience tabs with animated transitions
- [ ] DISARM matrix preview with wave animation
- [ ] Education preview with gamification showcase
- [ ] Pricing cards with monthly/yearly toggle
- [ ] Final CTA with waitlist email collection
- [ ] Footer with proper link structure
- [ ] Grid background pattern throughout
- [ ] All scroll-triggered reveal animations
- [ ] Reduced motion fallbacks
- [ ] Mobile responsive (all sections)
- [ ] Lighthouse 90+ performance
- [ ] 3D scene lazy-loaded with suspense fallback
