"use client";

import { useState } from "react";
import { Check, X, Plus, Minus } from "lucide-react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";
import { ScrollReveal } from "@/components/landing/shared/ScrollReveal";

type BillingPeriod = "monthly" | "yearly";

interface Feature {
  text: string;
  included: boolean;
}

interface PricingPlan {
  name: string;
  monthlyPrice: string;
  yearlyPrice: string;
  features: Feature[];
  cta: string;
  ctaHref: string;
  riskReducer: string;
  popular?: boolean;
}

const plans: PricingPlan[] = [
  {
    name: "Free",
    monthlyPrice: "$0",
    yearlyPrice: "$0",
    features: [
      { text: "10 source checks per month", included: true },
      { text: "Basic plagiarism + AI detection", included: true },
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
    monthlyPrice: "$20",
    yearlyPrice: "$13",
    popular: true,
    features: [
      { text: "200 source checks per month", included: true },
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
    monthlyPrice: "Custom",
    yearlyPrice: "Custom",
    features: [
      { text: "Everything in Pro", included: true },
      { text: "Unlimited users + checks", included: true },
      { text: "Department dashboards", included: true },
      { text: "LMS integration", included: true },
      { text: "Batch analysis", included: true },
      { text: "SSO + custom branding", included: true },
      { text: "On-premise deployment", included: true },
    ],
    cta: "Contact sales",
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
    q: "What happens when free checks run out?",
    a: "You can upgrade anytime — your history is preserved. We don't auto-charge or downgrade you; you'll just see a gentle prompt the next time you try to start a check.",
  },
];

export function PricingSection() {
  const [billing, setBilling] = useState<BillingPeriod>("monthly");

  return (
    <section id="pricing" className="py-24 sm:py-28">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto mb-12 max-w-2xl text-center">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-fg-tertiary">
            Pricing
          </p>
          <h2 className="mt-3 font-display text-4xl font-semibold leading-[1.05] tracking-tight text-balance text-fg-primary sm:text-5xl">
            Free for the first ten checks.{" "}
            <span className="italic text-brand-fg">$20 if you keep going.</span>
          </h2>
        </div>

        <div className="mb-12 flex items-center justify-center">
          <div className="inline-flex rounded-full border border-border-default bg-surface-card p-0.5">
            <button
              onClick={() => setBilling("monthly")}
              className={cn(
                "rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
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
                "rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
                billing === "yearly"
                  ? "bg-brand text-white"
                  : "text-fg-secondary hover:text-fg-primary",
              )}
            >
              Yearly · save 35%
            </button>
          </div>
        </div>

        <div className="mx-auto grid max-w-5xl grid-cols-1 gap-6 md:grid-cols-3">
          {plans.map((plan, idx) => (
            <ScrollReveal key={plan.name} delay={idx * 0.05}>
              <div
                className={cn(
                  "relative flex h-full flex-col rounded-xl border bg-surface-card p-7 transition-colors",
                  plan.popular
                    ? "border-brand/50"
                    : "border-border-default hover:border-border-strong",
                )}
              >
                {plan.popular && (
                  <span className="absolute right-7 top-7 inline-flex items-center rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-amber-700 dark:text-amber-300">
                    Most popular
                  </span>
                )}

                <h3 className="font-display text-lg font-semibold text-fg-primary">
                  {plan.name}
                </h3>

                <div className="mt-3 flex items-baseline gap-1">
                  <span className="font-display text-4xl font-semibold tabular-nums text-fg-primary">
                    {billing === "monthly"
                      ? plan.monthlyPrice
                      : plan.yearlyPrice}
                  </span>
                  {plan.monthlyPrice !== "Custom" && (
                    <span className="text-sm text-fg-tertiary">/mo</span>
                  )}
                </div>

                <div className="my-6 border-t border-border-subtle" />

                <ul className="flex-1 space-y-3">
                  {plan.features.map((feature) => (
                    <li
                      key={feature.text}
                      className="flex items-start gap-2 text-sm"
                    >
                      {feature.included ? (
                        <Check
                          size={14}
                          strokeWidth={2}
                          className="mt-0.5 shrink-0 text-brand-fg"
                          aria-label="Included"
                        />
                      ) : (
                        <X
                          size={14}
                          strokeWidth={1.5}
                          className="mt-0.5 shrink-0 text-fg-tertiary"
                          aria-label="Not included"
                        />
                      )}
                      <span
                        className={
                          feature.included
                            ? "text-fg-primary"
                            : "text-fg-tertiary"
                        }
                      >
                        {feature.text}
                      </span>
                    </li>
                  ))}
                </ul>

                <div className="mt-7">
                  <a
                    href={plan.ctaHref}
                    className={cn(
                      "inline-flex w-full items-center justify-center rounded-lg px-4 py-2.5 text-sm font-medium transition-all active:translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50",
                      plan.popular
                        ? "bg-brand text-white hover:bg-brand-hover"
                        : "border border-border-default text-fg-primary hover:bg-surface-base",
                    )}
                  >
                    {plan.cta}
                  </a>
                  <p className="mt-3 text-center text-xs text-fg-tertiary">
                    {plan.riskReducer}
                  </p>
                </div>
              </div>
            </ScrollReveal>
          ))}
        </div>

        <div className="mx-auto mt-20 max-w-3xl">
          <h3 className="mb-6 text-center font-display text-2xl font-semibold text-balance text-fg-primary">
            Pricing questions
          </h3>
          <FaqAccordion items={faqs} />
        </div>
      </div>
    </section>
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
    <div className="divide-y divide-border-subtle rounded-xl border border-border-default bg-surface-card">
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
              className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition-colors hover:bg-surface-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
            >
              <span className="text-sm font-semibold text-fg-primary">
                {faq.q}
              </span>
              <span
                aria-hidden="true"
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border-default text-fg-secondary"
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
                    duration: reduce ? 0 : 0.22,
                    ease: [0.16, 1, 0.3, 1],
                  }}
                  style={{ overflow: "hidden" }}
                >
                  <p className="px-5 pb-5 text-sm leading-relaxed text-fg-secondary">
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
