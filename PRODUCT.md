# Product

## Register

brand

## Users

Researchers, university administrators, and graduate students primarily across
Azerbaijan and the Eastern Partnership (EaP) region. The landing page also has
to land on cold institutional buyers — heads of research integrity offices,
deans, and grant program managers who arrive expecting either trust signals or
a quick disqualification.

Their context: arriving from a search query, an email link, or a peer-shared
URL, often on a shared institutional laptop with a slow connection, sometimes
on a projector during a faculty meeting. They've seen Turnitin and GPTZero;
they're skeptical of "AI-detection" pitches. The job to be done is *decide
whether ArtiProof is credible enough to upload an actual paper to it.*

## Product Purpose

ArtiProof is a research-integrity platform that runs five integrity engines on
a single submission — plagiarism, AI content detection, citation-ring
detection, citation accessibility, and researcher-integrity scoring — and
returns a credibility score with a per-deduction breakdown that researchers
and committee members can defend in writing.

Success on the landing page = a researcher who's never heard of ArtiProof
runs their first analysis within 90 seconds of arriving. Secondary success =
a department head bookmarks the comparison or pricing page and emails it to
procurement.

## Brand Personality

Editorial authority. The voice of a Nature methods paper and the look of a
University Press monograph. Confident enough to use a serif on the headline,
specific enough to cite sources for every number. The accent (amber) appears
sparingly and intentionally; the brand color (oxblood / wine) carries
authority without shouting.

Three words: **rigorous, transparent, regional**. Regional matters: the
product is built for Azerbaijan and the EaP region first, and the landing
should signal that without being parochial.

## Anti-references

What this should explicitly *not* look like:

- **Generic dark-mode-emerald SaaS landing** with neon gradients,
  "AI-powered" subhead, and stock-photo founder quotes. The whole reason the
  brand color is now wine, not emerald, is to escape this trap.
- **Turnitin-style enterprise legacy** — institutional-blue, stock photos
  of diverse students smiling at a laptop, "trusted since 1996" energy.
- **Crypto / VC pitch deck** — animated particles, big-number hero metrics
  in gradient text, "blazing-fast" copy.
- **Vercel-core dark Geist clone** — the new style is editorial, not
  bundler-marketing.
- **AI-slop tells**: gradient-text headlines, glassmorphism cards stacked
  inside other cards, identical icon-grids of features, side-stripe accent
  borders, hero metric template, animated count-up gimmicks.

## Design Principles

1. **Specific beats loud.** Numbers cite a source. Claims name an institution.
   "14,000 retractions / yr" with "Source: Retraction Watch" is more
   convincing than "Industry-leading accuracy".
2. **Show the artifact.** The hero shows the actual result page (score,
   claim verdicts, AI bar) — not an abstract globe or animation. A
   prospective user should be able to read a sample report from the hero.
3. **Restraint with one strong signal.** Wine carries every primary CTA
   and key brand emphasis. Amber appears only in places that genuinely
   want a second-tier accent (the "Most Popular" pricing badge,
   verdict highlights for misleading content). The brand surface should
   appear under 12% of any visible page area.
4. **Skepticism budget.** Each section either presents evidence (sourced
   stats, comparison table, scored sample) or earns the skeptic's next
   200 pixels of scroll. Avoid filler.
5. **Regional but not provincial.** Mention Azerbaijan / EaP / specific
   universities once or twice as proof of fit, not as the entire identity.

## Accessibility & Inclusion

- Target WCAG 2.1 AA. Foreground/background contrast ≥ 4.5:1 for body,
  ≥ 3:1 for large text and interactive components, in both light and dark
  mode.
- All animation respects `prefers-reduced-motion`. Reduced-motion users
  see content snap into place without translate or scale.
- Skip-to-content link visible on focus. Live regions for SSE pipeline
  steps. Form labels associated via `htmlFor`.
- Score gauges expose `role="meter"` with `aria-valuenow`, `aria-valuemin`,
  `aria-valuemax`, `aria-valuetext`; progress bars use `role="progressbar"`.
- Theme toggle is keyboard-accessible, broadcasts state via `aria-pressed`,
  and the page announces theme changes via a polite live region.
- Both color modes designed first-class: light is not a desaturated
  inversion of dark, it's a separately-tuned cream / wine / charcoal
  palette with its own contrast budget.

## Localization

English only for now. Azerbaijani and Russian were aspirational and have
been de-scoped until a real next-intl scaffold ships — Next.js 16 removed
the `next.config` i18n shortcut and bolting on translation infrastructure
for zero current non-English users is a multi-week project we are not
ready to fund. The `User.locale` column and the settings selector stay
in place so the column doesn't need to be backfilled when i18n returns,
but the validator only accepts `en` and the selector only offers English.
