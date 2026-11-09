# Rebuild ArtiProof Landing Page From Scratch

## Instructions

Delete every file in `frontend/src/components/landing/`. Delete the landing page at `frontend/src/app/(landing)/page.tsx`. Rewrite `DESIGN.md` and `PRODUCT.md` at the project root to match the new design. Then rebuild the entire landing page from zero.

**Before writing a single line of code:**

1. Run all your design skills — `/impeccable teach`, taste-skill, Emil Kowalski's animation skill, frontend-design skill, web-design-guidelines. Read every SKILL.md you have access to.
2. Let the skills pick a **bold, expressive color palette** that fits a research integrity platform. Do NOT default to emerald. Choose something distinctive. Document the new palette in `DESIGN.md`.
3. The theme must support **both dark and light mode** using `prefers-color-scheme` and a manual toggle. Design dark-first, then adapt for light.
4. Pick a display font pairing that has personality — not just Inter. Use Google Fonts. Document in `DESIGN.md`.

## What ArtiProof Is

A 5-in-1 research integrity platform: AI detection, plagiarism checking, citation ring detection, fact-checking with evidence, and researcher integrity scoring. Target users: researchers, PhD students, and universities in Azerbaijan and the Eastern Partnership region. Pricing: Free ($0, 10 checks/mo), Pro ($20/mo), Institution (custom/contact sales).

## Verified Stats (use these, they're real)

- 14,000+ papers retracted annually (Source: Retraction Watch)
- 92% of students have used AI tools (Source: HEPI Survey 2024)
- $392K average cost per retracted paper (Source: eLife Study)
- < 2 min average analysis time (Source: ArtiProof internal)
- 51 universities, 222,809 students across Azerbaijan
- Competitors: Turnitin ($3/student), GPTZero ($15/mo), Originality.ai ($15/mo), Copyleaks ($14/mo)

## Landing Page Sections (in order)

1. **Navbar** — Logo, 4-5 nav links, dark/light toggle, CTA button. Sticky, blurred background.
2. **Hero** — Bold headline, short subtitle, one primary CTA, one secondary. Show the actual product (browser mockup of results page with score, verdicts, AI bar). Make it visually stunning with purposeful animation.
3. **Social proof / trust bar** — Stats from above with source citations. Count-up animations on scroll.
4. **Interactive demo** — Let visitors click example URLs and see mock analysis results. Make the transition cinematic.
5. **Features** — Show all 5 engines. NOT an icon grid. Each feature needs a unique micro-visualization (animated chart, graph, gauge, etc). Use tabs, stacked alternating layout, or bento grid — pick what looks best.
6. **Comparison table** — ArtiProof vs Turnitin vs GPTZero vs Originality.ai. ArtiProof column highlighted.
7. **Pricing** — 3 tiers (Free/Pro/Institution). Monthly/yearly toggle. Pro highlighted as "Most Popular". Mini-FAQ below (security, accuracy, LMS integration, what happens when free runs out).
8. **Final CTA** — One last push. Single button with glow/emphasis.
9. **Footer** — 3 columns of real links. Logo + tagline. Copyright.

## Design Rules

- **Bold & expressive** — strong visual identity, confident typography, animated interactions, eye-catching hero. This should NOT look like a template.
- **Every animation must respect `prefers-reduced-motion`.**
- **No fake data.** Only use the verified stats above.
- **No "AI-powered" or "blazing-fast" marketing speak.** The copy should be specific and evidence-based.
- **Show the product.** The hero must display the actual analysis result (score, claim verdicts, AI detection bar), not an abstract illustration.
- **Mobile-first.** Every section must work perfectly at 375px.
- **Accessibility.** WCAG 2.1 AA contrast, skip-to-content, ARIA labels, focus-visible on all interactive elements.

## After Building

1. Run `/impeccable audit` on the full page.
2. Run `/impeccable polish` on each section.
3. Verify `npm run build` passes with zero errors.
4. Verify dark mode and light mode both look correct.
5. Verify mobile layout at 375px.
6. Update `DESIGN.md` and `PRODUCT.md` to reflect all new design decisions.

**Don't stop until everything is done and all audits pass.**
