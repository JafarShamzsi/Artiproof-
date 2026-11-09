# Phase 2: Landing Page Fixes
## Priority: CRITICAL + HIGH — Judges see this first

This phase fixes all incorrect information, outdated pricing, fake statistics, dead links, and missing sections on the ArtiProof landing page. The landing page is the first thing hackathon judges see — it must be accurate and professional.

---

## Context

ArtiProof is a Research Integrity Platform with a freemium model:
- **Free:** $0, 10 checks/month
- **Pro:** $20/month, 200 checks/month, all 5 features
- **Institution:** Custom pricing (contact sales)

The platform has 5 core features that NO competitor offers together:
1. Plagiarism detection
2. AI content detection  
3. Citation ring detection (UNIQUE)
4. Integrity scoring (UNIQUE)
5. Fact-checking (UNIQUE)

Brand: ArtiProof (NOT CivicGuards). Color: Emerald #10B981. Dark theme.

---

## Issues To Fix (15 total)

### 1. Fix PricingSection — Wrong Prices
File: `frontend/src/components/landing/PricingSection.tsx`

**Current (WRONG):**
```typescript
const plans: PricingPlan[] = [
  {
    name: "Free — Researchers",
    monthlyPrice: "$0",
    yearlyPrice: "$0",
    popular: true,  // ← WRONG: Free shouldn't be "Most Popular"
    ...
  },
  {
    name: "Pro — Faculty",
    monthlyPrice: "$19",  // ← WRONG: Should be $20
    yearlyPrice: "$12",   // ← WRONG: Update yearly too
    ...
  },
  {
    name: "Institution",
    monthlyPrice: "Custom",
    yearlyPrice: "Custom",
    ...
  },
];
```

**Fix:**
- Change Pro `monthlyPrice` to `"$20"`
- Change Pro `yearlyPrice` to `"$13"` (or calculate: $20 × 12 × 0.65 / 12 ≈ $13)
- Move `popular: true` from Free to Pro (Pro should be highlighted — it's your revenue driver)
- Change Free features to match: "10 checks per month" (not "per day")
- Update Institution CTA to "Contact Sales"
- Update Pro features list to emphasize the 5-in-1 value

**Updated plans array:**
```typescript
const plans: PricingPlan[] = [
  {
    name: "Free",
    monthlyPrice: "$0",
    yearlyPrice: "$0",
    features: [
      { text: "10 source checks per month", included: true },
      { text: "Basic plagiarism detection", included: true },
      { text: "Basic AI content detection", included: true },
      { text: "Credibility scoring", included: true },
      { text: "Citation ring detection", included: false },
      { text: "Integrity scoring", included: false },
      { text: "PDF report export", included: false },
      { text: "API access", included: false },
    ],
    cta: "Get Started Free",
  },
  {
    name: "Pro",
    monthlyPrice: "$20",
    yearlyPrice: "$13",
    popular: true,
    features: [
      { text: "200 source checks per month", included: true },
      { text: "All 5 detection engines", included: true },
      { text: "Citation ring detection", included: true },
      { text: "Researcher integrity scoring", included: true },
      { text: "Fact-checking with evidence", included: true },
      { text: "PDF report generation", included: true },
      { text: "Citation graph visualization", included: true },
      { text: "API access", included: true },
    ],
    cta: "Start Pro",
  },
  {
    name: "Institution",
    monthlyPrice: "Custom",
    yearlyPrice: "Custom",
    features: [
      { text: "Everything in Pro", included: true },
      { text: "Unlimited users & checks", included: true },
      { text: "Department dashboards", included: true },
      { text: "LMS integration (Moodle, Canvas)", included: true },
      { text: "Batch analysis", included: true },
      { text: "SSO & custom branding", included: true },
      { text: "Dedicated support", included: true },
      { text: "On-premise deployment", included: true },
    ],
    cta: "Contact Sales",
  },
];
```

---

### 2. Fix ProblemSection — Fake/Wrong Statistics
File: `frontend/src/components/landing/ProblemSection.tsx`

**Current (WRONG/UNSOURCED):**
- "70% of researchers encounter misinformation" — NO SOURCE
- "30% of academic citations involve self-citation manipulation" — NO SOURCE
- "10K+" papers retracted — WRONG, should be 14,000+
- "< 2min" to verify — OK to keep

**Fix with REAL, verified statistics:**

```typescript
export function ProblemSection() {
  return (
    <section className="w-full border-y border-zinc-800 bg-zinc-900/50 py-16">
      <div className="mx-auto grid max-w-7xl grid-cols-2 gap-8 px-6 md:grid-cols-4">
        <ScrollReveal delay={0} className="text-center">
          <div className="text-4xl font-bold text-white md:text-5xl">
            <AnimatedCounter value={14} suffix="K+" />
          </div>
          <p className="mx-auto mt-2 max-w-[200px] text-sm text-zinc-400">
            papers retracted in 2023 alone — a record high
          </p>
        </ScrollReveal>

        <ScrollReveal delay={0.1} className="text-center">
          <div className="text-4xl font-bold text-white md:text-5xl">
            <AnimatedCounter value={92} suffix="%" />
          </div>
          <p className="mx-auto mt-2 max-w-[200px] text-sm text-zinc-400">
            of students have used generative AI on assignments
          </p>
        </ScrollReveal>

        <ScrollReveal delay={0.2} className="text-center">
          <div className="text-4xl font-bold text-emerald-400 md:text-5xl">
            $392K
          </div>
          <p className="mx-auto mt-2 max-w-[200px] text-sm text-zinc-400">
            average cost per retracted paper to institutions
          </p>
        </ScrollReveal>

        <ScrollReveal delay={0.3} className="text-center">
          <div className="text-4xl font-bold text-white md:text-5xl">
            &lt; 2min
          </div>
          <p className="mx-auto mt-2 max-w-[200px] text-sm text-zinc-400">
            to verify any article or research source
          </p>
        </ScrollReveal>
      </div>
    </section>
  );
}
```

Sources for these numbers:
- 14,000+ retractions: Retraction Watch, 2023
- 92% student AI use: HEPI Survey, 2024
- $392K per retraction: eLife study, 2023

---

### 3. Fix FeaturesSection — Wrong Messaging
File: `frontend/src/components/landing/FeaturesSection.tsx`

**Current (WRONG):** The last feature card says:
```
"Free for academic researchers and institutions. Built by EaP Guardians to protect the integrity of knowledge worldwide."
```

This contradicts the paid pricing model.

**Fix:** Change the last feature card:
```typescript
{
  icon: Heart,
  title: "Built for the EaP Region",
  description:
    "Purpose-built for Azerbaijan and Eastern Partnership universities. Native Azerbaijani and Russian language support, local compliance, and pricing designed for the region.",
  visual: <APISnippet />,
  colSpan: "lg:col-span-3",
  glowColor: "emerald",
},
```

---

### 4. Fix Dead Footer Links
File: `frontend/src/components/landing/Footer.tsx`

15+ links point to `#`. Judges will click these.

**Fix:** Either:
- (a) Remove sections that don't exist yet (Blog, Careers, Press Kit)
- (b) Point them to relevant sections on the landing page

**Recommended approach — simplify the footer:**
```typescript
const productLinks = [
  { label: "Source Verification", href: "#features" },
  { label: "AI Detection", href: "#features" },
  { label: "Citation Analysis", href: "#features" },
  { label: "Pricing", href: "#pricing" },
];

const companyLinks = [
  { label: "About", href: "#how-it-works" },
  { label: "Contact", href: "mailto:info@artiproof.com" },
];

const legalLinks = [
  { label: "Privacy Policy", href: "/privacy" },
  { label: "Terms of Service", href: "/terms" },
];
```

Create placeholder pages at `frontend/src/app/(landing)/privacy/page.tsx` and `terms/page.tsx` with minimal content so the links don't 404.

---

### 5. Update Hero Section Social Proof
File: `frontend/src/components/landing/HeroSection.tsx`

**Current:**
```
Built for researchers, faculty, and institutions worldwide
```

**Fix — add real numbers:**
```typescript
<motion.p {...animationProps(0.9)} className="mt-12 text-sm text-zinc-500">
  Targeting{" "}
  <span className="text-zinc-400">51 universities</span> and{" "}
  <span className="text-zinc-400">222,809 students</span> across{" "}
  <span className="text-zinc-400">Azerbaijan & the EaP region</span>
</motion.p>
```

---

### 6. Update CTA Section
File: `frontend/src/components/landing/CTASection.tsx`

**Current:**
```
"Free for academic researchers worldwide."
```

**Fix:**
```typescript
<p className="mt-4 text-zinc-400">
  Start with 10 free checks per month. Upgrade to Pro for full access
  to all 5 integrity engines.
</p>
```

And update the bottom text:
```typescript
<p className="mt-6 text-sm text-zinc-500">
  Built by the ArtiProof team for the EaP region
</p>
```

---

### 7. Add a Trust/Stats Bar Section
Create a new component: `frontend/src/components/landing/TrustSection.tsx`

This goes between HeroSection and ProblemSection. It adds credibility with real market context.

```typescript
"use client";

import { ScrollReveal } from "./shared/ScrollReveal";
import { SectionHeading } from "./shared/SectionHeading";

const competitors = [
  { name: "Turnitin", features: "2 of 5", price: "$3.19/student" },
  { name: "GPTZero", features: "1 of 5", price: "$24/mo" },
  { name: "Copyleaks", features: "2 of 5", price: "$14-75/mo" },
  { name: "ArtiProof", features: "5 of 5", price: "$20/mo", highlight: true },
];

export function TrustSection() {
  return (
    <section className="py-16">
      <div className="mx-auto max-w-5xl px-6">
        <SectionHeading
          eyebrow="WHY ARTIPROOF"
          title="More Features, Better Price"
          gradient="Price"
        />
        <ScrollReveal>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="pb-3 text-left text-zinc-400 font-medium">Platform</th>
                  <th className="pb-3 text-center text-zinc-400 font-medium">Features</th>
                  <th className="pb-3 text-right text-zinc-400 font-medium">Price</th>
                </tr>
              </thead>
              <tbody>
                {competitors.map((c) => (
                  <tr
                    key={c.name}
                    className={`border-b border-zinc-800/50 ${c.highlight ? "bg-emerald-500/5" : ""}`}
                  >
                    <td className={`py-3 font-medium ${c.highlight ? "text-emerald-400" : "text-white"}`}>
                      {c.name}
                    </td>
                    <td className="py-3 text-center text-zinc-400">{c.features}</td>
                    <td className={`py-3 text-right ${c.highlight ? "text-emerald-400 font-semibold" : "text-zinc-400"}`}>
                      {c.price}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
```

Add it to the landing page in `frontend/src/app/(landing)/page.tsx`:
```typescript
import { TrustSection } from "@/components/landing/TrustSection";

// In the JSX, after ProblemSection:
<ProblemSection />
<TrustSection />
<HowItWorksSection />
```

---

### 8. Clean Up Unused Components
Files: `frontend/src/components/landing/EngineGrid.tsx`, `frontend/src/components/landing/EducationSection.tsx`

Check if these are imported anywhere. If not, either:
- Integrate EngineGrid into the FeaturesSection (it may have good content)
- Remove both if they're truly unused and outdated

---

### 9. Fix Container Name Mismatch
File: `run.sh`

**Current:** References `civicguards-postgres` and `civicguards-redis`
**Docker-compose:** Uses `artiproof-postgres` and `artiproof-redis` (or similar)

**Fix:** Update run.sh to match docker-compose.yml container names.

---

## Verification

After completing all fixes:
1. Landing page pricing shows: Free ($0), Pro ($20/mo, highlighted), Institution (Custom)
2. Stats bar shows: 14K+, 92%, $392K, < 2min
3. No mention of "free for researchers and institutions" outside the Free tier
4. Footer links either work or are removed
5. Hero says "51 universities" and "222,809 students"
6. CTA mentions "10 free checks per month"
7. Trust comparison table shows ArtiProof winning on features
8. `run.sh` container names match `docker-compose.yml`
