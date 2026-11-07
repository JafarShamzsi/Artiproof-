"use client";

import { useState } from "react";
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
  numeral: string;
  monthlyPrice: string;
  yearlyPrice: string;
  features: Feature[];
  cta: string;
  ctaHref: string;
  riskReducer: string;
  popular?: boolean;
  /** Editorial subtitle for the tier ("for the curious", etc.). */
  subtitle: string;
}

const plans: PricingPlan[] = [
  {
    name: "Free",
    numeral: "I",
    subtitle: "for the curious",
    monthlyPrice: "$0",
    yearlyPrice: "$0",
    features: [
      { text: "10 source readings per month", included: true },
      { text: "Plagiarism + AI detection", included: true },
      { text: "Credibility scoring", included: true },
      { text: "Citation ring detection", included: false },
      { text: "Researcher integrity scoring", included: false },
      { text: "PDF report export", included: false },
      { text: "API access", included: false },
    ],
    cta: "Get started",
    ctaHref: "/register",
    riskReducer: "No credit card required",
  },
  {
    name: "Pro",
    numeral: "II",
    subtitle: "the working researcher",
    monthlyPrice: "$20",
    yearlyPrice: "$13",
    popular: true,
    features: [
      { text: "200 readings per month", included: true },
      { text: "All five integrity engines", included: true },
      { text: "Citation ring detection", included: true },
      { text: "Researcher integrity scoring", included: true },
      { text: "Fact-checking with evidence", included: true },
      { text: "PDF report generation", included: true },
      { text: "API access", included: true },
    ],
    cta: "Start Pro",
    ctaHref: "/register?plan=pro",
    riskReducer: "Cancel anytime · 14-day refund",
  },
  {
    name: "Institution",
    numeral: "III",
    subtitle: "the university press",
    monthlyPrice: "Custom",
    yearlyPrice: "Custom",
    features: [
      { text: "Everything in Pro", included: true },
      { text: "Unlimited users + readings", included: true },
      { text: "Department dashboards", included: true },
      { text: "LMS integration", included: true },
      { text: "Batch analysis", included: true },
      { text: "SSO + custom branding", included: true },
      { text: "On-premise deployment", included: true },
    ],
    cta: "Contact the editors",
    ctaHref: "mailto:info@example.invalid",
    riskReducer: "Custom pricing · 30-day pilot",
  },
];

const faqs: { q: string; a: string }[] = [
  {
    q: "Is my data secure?",
    a: "Documents are encrypted in transit and at rest. We never store content after analysis completes — only the score breakdown and a hash for deduplication.",
  },
  {
    q: "How accurate is AI detection?",
    a: "Our multi-model approach achieves over 95% accuracy on benchmark sets. Detection is probabilistic — every result ships with a confidence level so you can interpret edge cases.",
  },
  {
    q: "Can I integrate with my LMS?",
    a: "API access is included on Pro and Institution plans. Native Moodle and Canvas plugins are available for Institution; LMS plugins for self-serve are on the Q3 2026 roadmap.",
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
          subtitle="Three tiers, set out plainly. No drip-pricing, no enterprise theater. The numbers below are exactly what you'll see at checkout."
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

function PlanRow({
  plan,
  billing,
}: {
  plan: PricingPlan;
  billing: BillingPeriod;
}) {
  return (
    <div
      className={cn(
        "relative grid grid-cols-1 gap-x-12 gap-y-6 px-1 py-10 transition-colors lg:grid-cols-[6.5rem_minmax(0,1.1fr)_minmax(0,1.2fr)_auto] lg:items-start lg:py-12",
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

      {/* CTA */}
      <div className="flex flex-col items-start gap-2 lg:items-end lg:text-right">
        <a
          href={plan.ctaHref}
          className={cn(
            "inline-flex w-full items-center justify-center rounded-sm px-5 py-3 text-sm font-medium transition-all active:translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50 lg:w-auto",
            plan.popular
              ? "cta-glow bg-brand text-white shadow-[0_8px_24px_-8px_color-mix(in_oklab,var(--brand)_60%,transparent)] hover:bg-brand-hover"
              : "border border-border-strong text-fg-primary hover:bg-surface-card",
          )}
        >
          {plan.cta}
        </a>
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
