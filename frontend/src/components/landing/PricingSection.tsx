"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, X, Plus, Minus } from "lucide-react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";
import { ScrollReveal } from "@/components/landing/shared/ScrollReveal";
import { ChapterHeading } from "@/components/landing/shared/ChapterHeading";

type BillingPeriod = "monthly" | "yearly";

interface Feature {
  text: string;
  included: boolean;
}

interface PricingPlan {
  name: string;
  /** Stable id used as the URL fragment anchor (e.g. `/pricing#team`). */
  slug: string;
  numeral: string;
  monthlyPrice: string;
  yearlyPrice: string;
  /** Optional sub-line under the headline price (e.g. seat bracket). */
  priceSuffix?: string;
  features: Feature[];
  cta: string;
  ctaHref: string;
  riskReducer: string;
  popular?: boolean;
  /** Editorial subtitle for the tier ("for the curious", etc.). */
  subtitle: string;
}

export const PRICING_PLANS: PricingPlan[] = [
  {
    name: "Free",
    slug: "free",
    numeral: "I",
    subtitle: "for the curious",
    monthlyPrice: "$0",
    yearlyPrice: "$0",
    features: [
      { text: "10 source readings per month", included: true },
      { text: "Paragraph-level AI style estimates", included: true },
      { text: "Credibility scoring", included: true },
      { text: "5 researcher analyses per month", included: true },
      { text: "5 PDF reports per month", included: true },
      { text: "Citation and self-citation analysis", included: true },
      { text: "API access", included: false },
    ],
    cta: "Get started",
    ctaHref: "/register",
    riskReducer: "No credit card required",
  },
  {
    name: "Pro",
    slug: "pro",
    numeral: "II",
    subtitle: "the working researcher",
    monthlyPrice: "$20",
    yearlyPrice: "$13",
    popular: true,
    features: [
      { text: "100 source readings per month", included: true },
      { text: "50 researcher analyses per month", included: true },
      { text: "Citation and self-citation analysis", included: true },
      { text: "Paragraph-level AI style estimates", included: true },
      { text: "Claim review with source links when available", included: true },
      { text: "50 PDF reports per month", included: true },
      { text: "Public API subscriptions", included: false },
    ],
    cta: "Register interest in Pro",
    ctaHref: "/register?plan=pro",
    riskReducer: "Registration starts on Free; paid activation is separate",
  },
  {
    name: "Team",
    slug: "team",
    numeral: "III",
    subtitle: "a research desk that ships together",
    monthlyPrice: "$99",
    yearlyPrice: "$79",
    priceSuffix: "starter · up to 10 seats",
    features: [
      { text: "Everything in Pro for every seat", included: true },
      { text: "Up to 10 seats (Starter) · 25 seats (Pro · $249/mo)", included: true },
      { text: "Shared watchlists + team activity feed", included: true },
      { text: "Role-based admin / member controls", included: true },
      { text: "Per-seat usage dashboard", included: true },
      { text: "Pooled report exports + branded PDFs", included: true },
      { text: "Audit log of every team action", included: true },
    ],
    cta: "Start a 14-day trial",
    ctaHref: "/dashboard?startTeam=1",
    riskReducer: "Free for 14 days · no card required",
  },
  {
    name: "Institution",
    slug: "institution",
    numeral: "IV",
    subtitle: "the university press",
    monthlyPrice: "Custom",
    yearlyPrice: "Custom",
    features: [
      { text: "Discuss a scoped institutional pilot", included: true },
      { text: "Agree seats, usage and retention before rollout", included: true },
      { text: "Department dashboards (planned)", included: false },
      { text: "Native LMS plugins (planned)", included: false },
      { text: "Institutional SSO (planned)", included: false },
      { text: "On-premise deployment (planned)", included: false },
      { text: "Dedicated support terms by agreement", included: true },
    ],
    cta: "Contact the editors",
    ctaHref: "/contact-sales?plan=institution",
    riskReducer: "Scope and commercial terms by agreement",
  },
];

// Back-compat alias for callers that imported the old name.
const plans = PRICING_PLANS;

const faqs: { q: string; a: string }[] = [
  {
    q: "Is my data secure?",
    a: "Submitted text, uploaded PDFs and analysis findings are stored to support your history and reports. Deletion follows the service's retention process; content is not automatically discarded when analysis finishes.",
  },
  {
    q: "How accurate is AI detection?",
    a: "AI style estimates can be wrong and are not proof of authorship or misconduct. The analysis samples up to 20 paragraphs and may use a heuristic fallback. We have not published a validated accuracy benchmark.",
  },
  {
    q: "Can I integrate with my LMS?",
    a: "Native Moodle and Canvas plugins are planned and are not available in the current product. Contact us to discuss integration requirements before including them in a rollout.",
  },
  {
    q: "What happens when free readings run out?",
    a: "You can upgrade anytime — your history is preserved. We don't auto-charge or downgrade you; you'll just see a gentle prompt the next time you try to start a reading.",
  },
];

export function PricingSection() {
  const [billing, setBilling] = useState<BillingPeriod>("monthly");

  return (
    <section id="pricing" className="py-28 sm:py-32">
      <div className="mx-auto max-w-7xl px-6">
        <ChapterHeading
          numeral="V"
          eyebrow="Subscription"
          title={
            <>
              Free for the first ten readings.{" "}
              <span className="italic text-brand-fg">$20 if you keep going.</span>
            </>
          }
          subtitle="Start on Free. Pro prices are proposed; registration does not activate a paid subscription. Institutional capabilities and terms require a scoped agreement."
        />

        {/* Billing toggle */}
        <div className="mt-12 flex items-center justify-start">
          <div className="inline-flex rounded-sm border border-border-default bg-surface-card p-0.5">
            <button
              onClick={() => setBilling("monthly")}
              className={cn(
                "rounded-sm px-4 py-1.5 text-sm font-medium transition-colors",
                billing === "monthly"
                  ? "bg-brand text-white"
                  : "text-fg-secondary hover:text-fg-primary",
              )}
            >
              Monthly
            </button>
            <button
              onClick={() => setBilling("yearly")}
              className={cn(
                "rounded-sm px-4 py-1.5 text-sm font-medium transition-colors",
                billing === "yearly"
                  ? "bg-brand text-white"
                  : "text-fg-secondary hover:text-fg-primary",
              )}
            >
              Yearly · save 35%
            </button>
          </div>
        </div>

        {/* Tiers — laid out as a vertically-divided syllabus rather than
            three card boxes. Each tier is a row in a typographic table. */}
        <div className="mt-12 overflow-hidden">
          {/* Top doubled rule */}
          <hr className="rule-double" />

          <div className="divide-y divide-border-subtle">
            {plans.map((plan, idx) => (
              <ScrollReveal key={plan.name} delay={idx * 0.05}>
                <PlanRow plan={plan} billing={billing} />
              </ScrollReveal>
            ))}
          </div>

          {/* Bottom doubled rule */}
          <hr className="rule-double" />
        </div>

        <div className="mx-auto mt-24 max-w-3xl">
          <div className="mb-8 flex items-center gap-3">
            <span aria-hidden="true" className="h-px w-7 bg-border-strong" />
            <span className="label-eyebrow text-brand-fg">
              Frequently asked
            </span>
            <span aria-hidden="true" className="h-px flex-1 bg-border-strong" />
          </div>
          <FaqAccordion items={faqs} />
        </div>
      </div>
    </section>
  );
}

export function PlanRow({
  plan,
  billing,
}: {
  plan: PricingPlan;
  billing: BillingPeriod;
}) {
  return (
    <div
      id={plan.slug}
      // `scroll-mt-24` keeps the anchor target visible below any fixed
      // header when /pricing#team / #pro / etc. is loaded directly.
      className={cn(
        "relative grid scroll-mt-24 grid-cols-1 gap-x-12 gap-y-6 px-1 py-10 transition-colors lg:grid-cols-[6.5rem_minmax(0,1.1fr)_minmax(0,1.2fr)_auto] lg:items-start lg:py-12",
        plan.popular && "bg-brand-soft/25",
      )}
    >
      {/* Faint left numeral */}
      <div className="flex flex-col gap-2 lg:items-start">
        <span
          aria-hidden="true"
          className="numeral-chapter pointer-events-none select-none"
          style={{ opacity: 0.6 }}
        >
          {plan.numeral}
        </span>
        {plan.popular && (
          <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-brand-fg">
            ◆ House choice
          </span>
        )}
      </div>

      {/* Plan title + price */}
      <div>
        <h3 className="font-display text-3xl font-semibold tracking-tight text-fg-primary sm:text-4xl">
          {plan.name}
        </h3>
        <p className="editorial-italic mt-1 text-base text-fg-secondary">
          — {plan.subtitle}
        </p>

        <div className="mt-6 flex items-baseline gap-1.5">
          <span className="font-display text-5xl font-semibold tabular-nums tracking-tight text-fg-primary">
            {billing === "monthly" ? plan.monthlyPrice : plan.yearlyPrice}
          </span>
          {plan.monthlyPrice !== "Custom" && (
            <span className="font-mono text-sm text-fg-tertiary">/ month</span>
          )}
        </div>
        {plan.priceSuffix && (
          <p className="mt-1 font-mono text-xs uppercase tracking-[0.18em] text-fg-tertiary">
            {plan.priceSuffix}
          </p>
        )}
      </div>

      {/* Feature list — tight, two-column on desktop */}
      <ul className="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        {plan.features.map((feature) => (
          <li key={feature.text} className="flex items-start gap-2.5">
            {feature.included ? (
              <Check
                size={14}
                strokeWidth={2}
                className="mt-1 shrink-0 text-brand-fg"
                aria-label="Included"
              />
            ) : (
              <X
                size={13}
                strokeWidth={1.5}
                className="mt-1 shrink-0 text-fg-tertiary"
                aria-label="Not included"
              />
            )}
            <span
              className={
                feature.included
                  ? "text-fg-primary"
                  : "text-fg-tertiary line-through decoration-border-default"
              }
            >
              {feature.text}
            </span>
          </li>
        ))}
      </ul>

      {/* CTA — Link so /register and /contact-sales navigate via the SPA. */}
      <div className="flex flex-col items-start gap-2 lg:items-end lg:text-right">
        <Link
          href={plan.ctaHref}
          className={cn(
            "inline-flex w-full items-center justify-center rounded-sm px-5 py-3 text-sm font-medium transition-all active:translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50 lg:w-auto",
            plan.popular
              ? "cta-glow bg-brand text-white shadow-[0_8px_24px_-8px_color-mix(in_oklab,var(--brand)_60%,transparent)] hover:bg-brand-hover"
              : "border border-border-strong text-fg-primary hover:bg-surface-card",
          )}
        >
          {plan.cta}
        </Link>
        <p className="editorial-italic w-full text-left text-xs text-fg-tertiary lg:text-right">
          {plan.riskReducer}
        </p>
      </div>
    </div>
  );
}

interface FaqItem {
  q: string;
  a: string;
}

function FaqAccordion({ items }: { items: readonly FaqItem[] }) {
  const [openIdx, setOpenIdx] = useState<number | null>(0);
  const reduce = useReducedMotion();

  return (
    <div className="divide-y divide-border-subtle border-y border-border-default">
      {items.map((faq, i) => {
        const isOpen = openIdx === i;
        const id = `faq-${i}`;
        return (
          <div key={faq.q}>
            <button
              type="button"
              onClick={() => setOpenIdx(isOpen ? null : i)}
              aria-expanded={isOpen}
              aria-controls={id}
              className="flex w-full items-center justify-between gap-5 px-1 py-5 text-left transition-colors hover:bg-surface-card/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
            >
              <span className="flex items-baseline gap-3">
                <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-fg-tertiary">
                  Q{String(i + 1).padStart(2, "0")}
                </span>
                <span className="font-display text-lg font-medium text-fg-primary sm:text-xl">
                  {faq.q}
                </span>
              </span>
              <span
                aria-hidden="true"
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border-default text-fg-secondary"
              >
                {isOpen ? (
                  <Minus className="h-3.5 w-3.5" strokeWidth={1.5} />
                ) : (
                  <Plus className="h-3.5 w-3.5" strokeWidth={1.5} />
                )}
              </span>
            </button>
            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  id={id}
                  key="content"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{
                    duration: reduce ? 0 : 0.26,
                    ease: [0.16, 1, 0.3, 1],
                  }}
                  style={{ overflow: "hidden" }}
                >
                  <p className="editorial-italic max-w-2xl pb-5 pl-12 pr-1 text-base leading-relaxed text-fg-secondary">
                    {faq.a}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}
