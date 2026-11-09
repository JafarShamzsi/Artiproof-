# Phase 10: Design Overhaul
## Priority: CRITICAL — Transform from prototype to investor-ready product

This phase transforms ArtiProof from a "developer prototype" design into a professional, polished SaaS product. Based on analysis of 50+ YC startup landing pages, competitor products (GPTZero, Originality.ai, iThenticate, Copyleaks), Linear's design system, and 2026 SaaS design trends.

**Brand:** ArtiProof (NOT CivicGuards)
**Primary Color:** Emerald #10B981
**Background:** Near-black #0a0a0a (zinc-950)
**Font Stack:** Inter (body) + display font for headlines (see Section 1)

---

## Section 1: Brand & Design System Foundation (Do First)

### 1.1 Add Display Font for Headlines

Install a display font to create visual hierarchy. Inter is great for body text but too neutral for headlines.

File: `frontend/src/app/layout.tsx`

```typescript
import { Inter, Plus_Jakarta_Sans } from "next/font/google";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jakarta = Plus_Jakarta_Sans({ 
  subsets: ["latin"], 
  variable: "--font-display",
  weight: ["500", "600", "700", "800"]
});

// In <body>:
<body className={`${inter.variable} ${jakarta.variable} font-sans`}>
```

File: `frontend/tailwind.config.ts`

```typescript
theme: {
  extend: {
    fontFamily: {
      sans: ["var(--font-inter)", "system-ui", "sans-serif"],
      display: ["var(--font-display)", "var(--font-inter)", "system-ui", "sans-serif"],
    },
  },
}
```

Use `font-display` for: landing page headlines, section titles, pricing tier names, dashboard page titles.

### 1.2 Define Design Tokens

Create: `frontend/src/lib/design-tokens.ts`

```typescript
// ============ COLOR TOKENS ============
export const colors = {
  // Surfaces
  surface: {
    primary: "bg-zinc-950",       // Main background
    secondary: "bg-zinc-900",     // Cards, panels
    tertiary: "bg-zinc-800",      // Hover states, nested elements
    elevated: "bg-zinc-900/80 backdrop-blur-xl", // Floating elements
  },
  
  // Text
  text: {
    primary: "text-white",
    secondary: "text-zinc-400",
    tertiary: "text-zinc-500",
    inverse: "text-zinc-950",
  },
  
  // Brand
  brand: {
    primary: "text-emerald-400",
    primaryBg: "bg-emerald-500",
    primaryHover: "hover:bg-emerald-600",
    primaryGhost: "bg-emerald-500/10 text-emerald-400",
    primaryBorder: "border-emerald-500/20",
  },
  
  // Semantic
  success: { text: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20" },
  warning: { text: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20" },
  error: { text: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20" },
  info: { text: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/20" },
  
  // Borders
  border: {
    default: "border-zinc-800",
    subtle: "border-zinc-800/50",
    strong: "border-zinc-700",
  },
} as const;

// ============ SPACING SCALE ============
// Base: 4px. Use Tailwind classes: 1=4px, 2=8px, 3=12px, 4=16px, 6=24px, 8=32px, 12=48px, 16=64px
export const spacing = {
  section: "py-24 md:py-32",      // Between landing page sections
  sectionInner: "py-16 md:py-24", // Inside sections
  card: "p-6",                    // Card padding
  cardCompact: "p-4",             // Compact card padding
  stack: "space-y-6",             // Standard vertical spacing
  stackTight: "space-y-3",       // Tight vertical spacing
  stackLoose: "space-y-12",      // Loose vertical spacing
} as const;

// ============ TYPOGRAPHY SCALE ============
export const typography = {
  // Landing page
  hero: "font-display text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight",
  sectionTitle: "font-display text-3xl sm:text-4xl font-bold tracking-tight",
  sectionSubtitle: "text-lg sm:text-xl text-zinc-400 max-w-2xl",
  eyebrow: "text-sm font-medium text-emerald-400 tracking-wide uppercase",
  
  // Dashboard
  pageTitle: "font-display text-2xl font-bold text-white",
  cardTitle: "text-sm font-medium text-zinc-300",
  cardValue: "text-2xl font-bold text-white",
  label: "text-xs font-medium text-zinc-500 uppercase tracking-wider",
  body: "text-sm text-zinc-400",
  caption: "text-xs text-zinc-500",
} as const;

// ============ MOTION TOKENS ============
export const motion = {
  fast: { duration: 0.15, ease: [0.16, 1, 0.3, 1] },
  normal: { duration: 0.3, ease: [0.16, 1, 0.3, 1] },
  slow: { duration: 0.5, ease: [0.16, 1, 0.3, 1] },
  spring: { type: "spring", stiffness: 300, damping: 30 },
} as const;

// ============ BORDER RADIUS ============
export const radius = {
  sm: "rounded-md",      // Buttons, inputs
  md: "rounded-lg",      // Cards
  lg: "rounded-xl",      // Large cards, modals
  xl: "rounded-2xl",     // Hero elements
  full: "rounded-full",  // Badges, avatars
} as const;
```

### 1.3 Define Button Component Variants

Create or update: `frontend/src/components/ui/button.tsx`

Ensure these variants exist (if using shadcn, update the variants):

```typescript
const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-lg text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-emerald-500 text-white hover:bg-emerald-600 shadow-lg shadow-emerald-500/20",
        secondary: "bg-zinc-800 text-zinc-100 hover:bg-zinc-700 border border-zinc-700",
        ghost: "text-zinc-400 hover:text-white hover:bg-zinc-800/50",
        outline: "border border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:text-white",
        destructive: "bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-base",
        xl: "h-14 px-8 text-base",  // For landing page CTAs
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  }
);
```

---

## Section 2: Landing Page Redesign

### 2.1 Replace Hero Section

File: `frontend/src/components/landing/HeroSection.tsx`

**Current:** Descriptive headline + animated globe + two CTAs
**Target:** Outcome-driven headline + product screenshot + single dominant CTA + social proof

Key changes:
```typescript
// HEADLINE: Change from descriptive to outcome-driven
// OLD: "Research Integrity Platform"
// NEW: One of these options:

// Option A (trust-focused):
"Know If You Can Trust the Research"

// Option B (action-focused):
"Catch Scientific Fraud Before Publication"

// Option C (problem-focused):
"14,000 Papers Retracted Last Year. Was Yours Cited?"

// SUBHEADLINE:
"5 integrity checks in one platform — AI detection, plagiarism, citation rings, fact-checking, and researcher scoring. Trusted by researchers across 51 universities."

// CTA: Single dominant button
<button className="h-14 px-8 bg-emerald-500 text-white text-base font-semibold rounded-xl hover:bg-emerald-600 shadow-lg shadow-emerald-500/25 transition-all">
  Start Free Analysis
</button>
<p className="text-xs text-zinc-500 mt-2">No credit card required · 10 free checks/month</p>

// SOCIAL PROOF BAR (directly below CTA):
<div className="flex items-center gap-6 mt-8">
  <div className="flex -space-x-2">
    {/* 4-5 avatar circles */}
  </div>
  <div>
    <div className="flex items-center gap-1">
      {/* 5 star icons in amber */}
      <span className="text-sm text-zinc-400 ml-1">from 200+ researchers</span>
    </div>
  </div>
</div>
```

**Replace the animated globe** with a product screenshot or interactive demo:

```typescript
// RIGHT SIDE: Show actual product instead of decorative globe
<div className="relative">
  {/* Browser chrome mockup */}
  <div className="rounded-xl border border-zinc-800 bg-zinc-900 overflow-hidden shadow-2xl shadow-black/50">
    <div className="flex items-center gap-1.5 px-4 py-3 border-b border-zinc-800">
      <div className="w-3 h-3 rounded-full bg-red-500/60" />
      <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
      <div className="w-3 h-3 rounded-full bg-green-500/60" />
      <span className="ml-3 text-xs text-zinc-500">app.artiproof.com/check/results</span>
    </div>
    {/* Screenshot or live component showing check results */}
    <div className="p-4">
      {/* Render a mini version of the results page */}
    </div>
  </div>
  
  {/* Floating badge */}
  <div className="absolute -bottom-4 -left-4 rounded-lg bg-zinc-900 border border-zinc-800 px-3 py-2 shadow-xl">
    <div className="flex items-center gap-2">
      <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center">
        <span className="text-emerald-400 text-sm font-bold">92</span>
      </div>
      <div>
        <p className="text-xs font-medium text-white">Credibility Score</p>
        <p className="text-[10px] text-zinc-500">High confidence</p>
      </div>
    </div>
  </div>
</div>
```

### 2.2 Remove FallingStars — Replace with Gradient Mesh

File: `frontend/src/app/(landing)/page.tsx`

Remove the FallingStars component. Replace with a subtle gradient background:

```typescript
// Remove: <FallingStars />

// Add to the landing page wrapper:
<div className="relative">
  {/* Gradient mesh background */}
  <div className="fixed inset-0 -z-10">
    <div className="absolute top-0 left-1/4 w-96 h-96 bg-emerald-500/5 rounded-full blur-[128px]" />
    <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-blue-500/5 rounded-full blur-[128px]" />
    <div className="absolute bottom-1/3 left-1/3 w-96 h-96 bg-purple-500/3 rounded-full blur-[128px]" />
  </div>
  
  {/* Grid pattern overlay */}
  <div className="fixed inset-0 -z-10 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:64px_64px]" />
  
  {/* Content */}
  {children}
</div>
```

### 2.3 Add Trust Section (Social Proof)

Create: `frontend/src/components/landing/TrustSection.tsx`

Place this DIRECTLY after the hero section (before ProblemSection):

```typescript
export function TrustSection() {
  return (
    <section className="py-12 border-y border-zinc-800/50">
      <div className="max-w-6xl mx-auto px-6">
        {/* Logo strip */}
        <p className="text-center text-xs text-zinc-500 uppercase tracking-wider mb-8">
          Trusted by researchers at
        </p>
        <div className="flex items-center justify-center gap-8 md:gap-12 opacity-40 hover:opacity-60 transition-opacity">
          {/* University/institution logos or names */}
          {/* Use grayscale filter, hover to reveal color */}
          {institutions.map(inst => (
            <span key={inst} className="text-sm font-medium text-zinc-400 whitespace-nowrap">
              {inst}
            </span>
          ))}
        </div>
        
        {/* Stats bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mt-12 pt-8 border-t border-zinc-800/50">
          {[
            { value: "14,000+", label: "Retractions detected annually", source: "Retraction Watch" },
            { value: "92%", label: "Students using AI tools", source: "HEPI Survey 2024" },
            { value: "$392K", label: "Cost per retracted paper", source: "eLife Study" },
            { value: "< 2min", label: "Average analysis time", source: "ArtiProof data" },
          ].map(stat => (
            <div key={stat.label} className="text-center">
              <div className="font-display text-3xl font-bold text-white">{stat.value}</div>
              <div className="text-sm text-zinc-400 mt-1">{stat.label}</div>
              <div className="text-[10px] text-zinc-600 mt-0.5">Source: {stat.source}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
```

### 2.4 Add Competitor Comparison Section

Create: `frontend/src/components/landing/ComparisonSection.tsx`

```typescript
const features = [
  { name: "Plagiarism Detection", artiproof: true, turnitin: true, gptzero: false, originality: true },
  { name: "AI Content Detection", artiproof: true, turnitin: true, gptzero: true, originality: true },
  { name: "Citation Ring Detection", artiproof: true, turnitin: false, gptzero: false, originality: false },
  { name: "Researcher Integrity Scoring", artiproof: true, turnitin: false, gptzero: false, originality: false },
  { name: "Fact-Checking with Sources", artiproof: true, turnitin: false, gptzero: false, originality: false },
  { name: "Self-Citation Analysis", artiproof: true, turnitin: false, gptzero: false, originality: false },
  { name: "Free Tier Available", artiproof: true, turnitin: false, gptzero: true, originality: false },
  { name: "Starting Price", artiproof: "$20/mo", turnitin: "$3/student", gptzero: "$15/mo", originality: "$15/mo" },
];

// Render as a clean comparison table with checkmarks (emerald) and X marks (zinc-600)
// ArtiProof column highlighted with emerald border and subtle bg
```

### 2.5 Redesign Section Transitions

Add gradient dividers between sections instead of hard cuts:

```typescript
// Between each landing page section, add:
<div className="h-px bg-gradient-to-r from-transparent via-zinc-800 to-transparent" />

// For major section breaks:
<div className="relative py-1">
  <div className="absolute inset-0 bg-gradient-to-b from-zinc-950 via-zinc-900/50 to-zinc-950" />
</div>
```

### 2.6 Upgrade Pricing Section

File: `frontend/src/components/landing/PricingSection.tsx`

Key changes:
- Pro tier gets "Most Popular" badge with emerald glow
- Add "No credit card required" under Free CTA
- Add "Cancel anytime" under Pro CTA
- Add mini-FAQ directly below pricing cards

```typescript
// Mini-FAQ beside pricing:
const faqs = [
  { q: "Is my data secure?", a: "Your documents are encrypted in transit and at rest. We never store your content after analysis." },
  { q: "How accurate is AI detection?", a: "Our multi-model approach achieves 95%+ accuracy. AI detection is probabilistic — we always show confidence levels." },
  { q: "Can I integrate with my LMS?", a: "API access is available on Pro and Institution plans. LMS plugins coming Q3 2026." },
  { q: "What happens when my free checks run out?", a: "You can upgrade anytime. Your history is preserved. No pressure — we'll remind you gently." },
];
```

### 2.7 Fix Footer

File: `frontend/src/components/landing/Footer.tsx`

Replace 15+ dead links with 3 columns of real links:

```typescript
const footerLinks = {
  Product: [
    { name: "Source Check", href: "/login" },
    { name: "Researcher Integrity", href: "/login" },
    { name: "Pricing", href: "#pricing" },
    { name: "API Docs", href: "/docs" },
  ],
  Company: [
    { name: "About", href: "/about" },
    { name: "Contact", href: "mailto:info@artiproof.com" },
    { name: "Privacy", href: "/privacy" },
    { name: "Terms", href: "/terms" },
  ],
  Resources: [
    { name: "How It Works", href: "#how-it-works" },
    { name: "Blog", href: "/blog" },
    { name: "Status", href: "https://status.artiproof.com" },
  ],
};
```

### 2.8 Add Navbar CTA

File: `frontend/src/components/landing/Navbar.tsx`

Add a persistent CTA button in the navbar:

```typescript
// In the navbar right side, add:
<a href="/register" className="hidden md:inline-flex h-9 px-4 items-center rounded-lg bg-emerald-500 text-sm font-medium text-white hover:bg-emerald-600 transition-colors shadow-sm shadow-emerald-500/20">
  Get Started Free
</a>
```

---

## Section 3: Dashboard UI Polish

### 3.1 Add Empty States

Create: `frontend/src/components/ui/empty-state.tsx`

```typescript
interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: { label: string; href: string };
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      <div className="w-12 h-12 rounded-xl bg-zinc-800 flex items-center justify-center text-zinc-500 mb-4">
        {icon}
      </div>
      <h3 className="text-sm font-medium text-white">{title}</h3>
      <p className="text-sm text-zinc-500 mt-1 text-center max-w-sm">{description}</p>
      {action && (
        <a href={action.href} className="mt-4 h-9 px-4 inline-flex items-center rounded-lg bg-emerald-500 text-sm font-medium text-white hover:bg-emerald-600">
          {action.label}
        </a>
      )}
    </div>
  );
}
```

Use in dashboard (when checks array is empty):
```typescript
<EmptyState
  icon={<Search className="w-5 h-5" />}
  title="No checks yet"
  description="Run your first source check to see results here."
  action={{ label: "Start a Check", href: "/check" }}
/>
```

### 3.2 Add Loading Skeletons

Create: `frontend/src/components/ui/skeleton.tsx`

```typescript
export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded-lg bg-zinc-800 ${className}`} />
  );
}

export function CardSkeleton() {
  return (
    <div className="rounded-lg border border-zinc-800 p-6 space-y-3">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <Skeleton className="h-10 flex-1" />
          <Skeleton className="h-10 w-24" />
          <Skeleton className="h-10 w-20" />
        </div>
      ))}
    </div>
  );
}
```

### 3.3 Upgrade Score Gauge

Replace the plain number score with a radial gauge:

```typescript
// Create: frontend/src/components/ui/score-gauge.tsx

interface ScoreGaugeProps {
  score: number;
  size?: number;
  label?: string;
}

export function ScoreGauge({ score, size = 120, label = "Credibility" }: ScoreGaugeProps) {
  const radius = (size - 16) / 2;
  const circumference = Math.PI * radius; // Half circle
  const offset = circumference - (score / 100) * circumference;
  
  const color = score >= 70 ? "#10b981" : score >= 40 ? "#eab308" : "#ef4444";
  const bgColor = score >= 70 ? "#10b98120" : score >= 40 ? "#eab30820" : "#ef444420";
  
  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size / 2 + 20} viewBox={`0 0 ${size} ${size / 2 + 20}`}>
        {/* Background arc */}
        <path
          d={`M 8 ${size/2 + 8} A ${radius} ${radius} 0 0 1 ${size - 8} ${size/2 + 8}`}
          fill="none"
          stroke={bgColor}
          strokeWidth={8}
          strokeLinecap="round"
        />
        {/* Score arc */}
        <path
          d={`M 8 ${size/2 + 8} A ${radius} ${radius} 0 0 1 ${size - 8} ${size/2 + 8}`}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-1000 ease-out"
        />
        {/* Score number */}
        <text x={size/2} y={size/2} textAnchor="middle" className="fill-white text-3xl font-bold font-display">
          {score}
        </text>
        <text x={size/2} y={size/2 + 16} textAnchor="middle" className="fill-zinc-500 text-xs">
          {label}
        </text>
      </svg>
    </div>
  );
}
```

### 3.4 Add Breadcrumbs

Create: `frontend/src/components/ui/breadcrumb.tsx`

```typescript
import Link from "next/link";
import { ChevronRight } from "lucide-react";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav className="flex items-center gap-1.5 text-sm mb-6">
      {items.map((item, i) => (
        <Fragment key={i}>
          {i > 0 && <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />}
          {item.href ? (
            <Link href={item.href} className="text-zinc-500 hover:text-zinc-300 transition-colors">
              {item.label}
            </Link>
          ) : (
            <span className="text-zinc-300">{item.label}</span>
          )}
        </Fragment>
      ))}
    </nav>
  );
}

// Usage in check/[id]/page.tsx:
<Breadcrumb items={[
  { label: "Dashboard", href: "/dashboard" },
  { label: "Source Checks", href: "/check" },
  { label: "Results" },
]} />
```

---

## Section 4: Visual Polish

### 4.1 Add Section Fade-In Animations

Create: `frontend/src/components/ui/fade-in.tsx`

```typescript
"use client";
import { motion } from "framer-motion";

export function FadeIn({ 
  children, 
  delay = 0,
  direction = "up" 
}: { 
  children: React.ReactNode;
  delay?: number;
  direction?: "up" | "down" | "left" | "right";
}) {
  const directionMap = {
    up: { y: 24 },
    down: { y: -24 },
    left: { x: 24 },
    right: { x: -24 },
  };
  
  return (
    <motion.div
      initial={{ opacity: 0, ...directionMap[direction] }}
      whileInView={{ opacity: 1, x: 0, y: 0 }}
      viewport={{ once: true, margin: "-100px" }}
      transition={{ duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}
```

Wrap all landing page sections:
```typescript
<FadeIn>
  <ProblemSection />
</FadeIn>
<FadeIn delay={0.1}>
  <HowItWorksSection />
</FadeIn>
```

### 4.2 Add Glow Effect to Primary CTA

```css
/* Add to globals.css */
.cta-glow {
  position: relative;
}
.cta-glow::after {
  content: "";
  position: absolute;
  inset: -1px;
  border-radius: inherit;
  background: linear-gradient(135deg, #10b981, #059669);
  z-index: -1;
  filter: blur(12px);
  opacity: 0.4;
  transition: opacity 0.3s;
}
.cta-glow:hover::after {
  opacity: 0.6;
}
```

### 4.3 Add Open Graph Meta Tags

File: `frontend/src/app/layout.tsx`

```typescript
export const metadata: Metadata = {
  title: "ArtiProof — Research Integrity Platform",
  description: "5-in-1 research integrity platform: AI detection, plagiarism checking, citation ring detection, researcher scoring, and fact-checking.",
  openGraph: {
    title: "ArtiProof — Know If You Can Trust the Research",
    description: "Catch scientific fraud before publication. 5 integrity checks in one platform.",
    url: "https://artiproof.com",
    siteName: "ArtiProof",
    images: [{ url: "/og-image.png", width: 1200, height: 630 }],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "ArtiProof — Research Integrity Platform",
    description: "5-in-1 research integrity: AI detection, plagiarism, citation rings, fact-checking, researcher scoring.",
    images: ["/og-image.png"],
  },
};
```

Create an OG image at `frontend/public/og-image.png` (1200x630px) showing the ArtiProof logo, tagline, and a product screenshot on dark background.

### 4.4 Enable Image Optimization

File: `frontend/next.config.ts`

```typescript
images: {
  unoptimized: false, // Enable Next.js image optimization
  remotePatterns: [
    { protocol: "https", hostname: "**.googleapis.com" },
  ],
},
```

---

## Section 5: Typography & Spacing Audit

### 5.1 Enforce Type Scale

Search and replace inconsistent text sizes throughout the codebase.

**Allowed sizes (body text):**
- `text-xs` (12px) — captions, timestamps, source labels
- `text-sm` (14px) — body text, table cells, descriptions
- `text-base` (16px) — emphasized body, input text
- `text-lg` (18px) — section subtitles (landing only)
- `text-xl` (20px) — card titles, dashboard page sections

**Allowed sizes (headings, with font-display):**
- `text-2xl` (24px) — dashboard page titles
- `text-3xl` (30px) — landing section titles (mobile)
- `text-4xl` (36px) — landing section titles (desktop)
- `text-5xl+` (48px+) — hero headline only

### 5.2 Enforce Spacing Scale

Replace arbitrary spacing with consistent scale:
- Between sections: `py-24` or `py-32`
- Card padding: `p-6` (standard) or `p-4` (compact)
- Stack items: `space-y-4` (tight) or `space-y-6` (normal) or `space-y-8` (loose)
- Heading to content: `mb-4` (always)
- Section title to grid: `mt-12` or `mt-16`

---

## Verification Checklist

### Landing Page
- [ ] Hero shows product screenshot, not decorative animation
- [ ] Hero headline is outcome-driven (not descriptive)
- [ ] Single dominant CTA with risk reducer text
- [ ] Social proof (logos or stats) visible within 1 scroll
- [ ] Competitor comparison section exists
- [ ] FallingStars replaced with gradient mesh
- [ ] Section transitions use gradient dividers
- [ ] Footer has only working links (no dead #)
- [ ] Navbar has persistent CTA button
- [ ] Pricing has "Most Popular" on Pro tier
- [ ] FAQ appears beside pricing

### Dashboard
- [ ] Empty states show on pages with no data
- [ ] Loading skeletons appear during data fetch
- [ ] Score uses radial gauge component
- [ ] Breadcrumbs on all nested pages
- [ ] All buttons use shared variant system

### Design System
- [ ] Display font loads for headlines
- [ ] Design tokens file exists and is imported
- [ ] Max 6 text sizes used across codebase
- [ ] Spacing follows 4px grid
- [ ] All colors use semantic token names
- [ ] OG meta tags render preview on social sharing
- [ ] Images optimized (unoptimized: false)

### Typography
- [ ] `grep -r "font-display" frontend/src/components/landing/` returns results for all section titles
- [ ] `grep -r "text-6xl\|text-7xl" frontend/src/` only appears in hero
- [ ] No `text-zinc-400` on headings (should be text-white or text-zinc-200)

### Motion
- [ ] FadeIn wrapper on all landing sections
- [ ] CTA has glow effect
- [ ] Reduced-motion media query respected
