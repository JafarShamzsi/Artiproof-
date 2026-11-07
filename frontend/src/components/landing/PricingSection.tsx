"use client";

import { useState } from "react";
import { Check, X } from "lucide-react";
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
      { text: "Basic plagiarism detection", included: true },
      { text: "Basic AI content detection", included: true },
      { text: "Credibility scoring", included: true },
      { text: "Citation ring detection", included: false },
      { text: "Integrity scoring", included: false },
      { text: "PDF report export", included: false },
      { text: "API access", included: false },
    ],
    cta: "Get Started Free",
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
      { text: "All 5 detection engines", included: true },
      { text: "Citation ring detection", included: true },
      { text: "Researcher integrity scoring", included: true },
      { text: "Fact-checking with evidence", included: true },
      { text: "PDF report generation", included: true },
      { text: "Citation graph visualization", included: true },
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
      { text: "Unlimited users & checks", included: true },
      { text: "Department dashboards", included: true },
      { text: "LMS integration (Moodle, Canvas)", included: true },
      { text: "Batch analysis", included: true },
      { text: "SSO & custom branding", included: true },
      { text: "Dedicated support", included: true },
      { text: "On-premise deployment", included: true },
    ],
    cta: "Contact Sales",
    ctaHref: "mailto:info@example.invalid",
    riskReducer: "Custom pricing · 30-day pilot",
  },
];

const faqs = [
  {
    q: "Is my data secure?",
    a: "Documents are encrypted in transit and at rest. We never store content after analysis completes — only the score breakdown and a hash for deduplication.",
  },
  {
    q: "How accurate is AI detection?",
    a: "Our multi-model approach achieves >95% accuracy on benchmark sets. Detection is probabilistic — every result ships with a confidence level so you can interpret edge cases.",
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
    <section id="pricing" className="py-24">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto mb-12 max-w-2xl text-center">
          <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">
            Pricing
          </p>
          <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Free for the first 10 checks. $20 if you keep going.
          </h2>
        </div>

        <div className="mb-12 flex items-center justify-center gap-1">
          <div className="inline-flex rounded-full border border-zinc-800 bg-zinc-900 p-1">
            <button
              onClick={() => setBilling("monthly")}
              className={cn(
                "rounded-full px-4 py-2 text-sm font-medium transition-colors",
                billing === "monthly"
                  ? "bg-white/10 text-white"
                  : "text-zinc-400 hover:text-zinc-300",
              )}
            >
              Monthly
            </button>
            <button
              onClick={() => setBilling("yearly")}
              className={cn(
                "rounded-full px-4 py-2 text-sm font-medium transition-colors",
                billing === "yearly"
                  ? "bg-white/10 text-white"
                  : "text-zinc-400 hover:text-zinc-300",
              )}
            >
              Yearly (Save 35%)
            </button>
          </div>
        </div>

        <div className="mx-auto grid max-w-5xl grid-cols-1 gap-6 md:grid-cols-3">
          {plans.map((plan, idx) => (
            <ScrollReveal key={plan.name} delay={idx * 0.05}>
              <div
                className={cn(
                  "relative h-full rounded-xl border bg-zinc-900/40 p-7 transition-colors",
                  plan.popular
                    ? "border-emerald-500/40"
                    : "border-zinc-800 hover:border-zinc-700",
                )}
              >
                {plan.popular && (
                  <span className="absolute right-7 top-7 inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-emerald-300">
                    Most popular
                  </span>
                )}

                <h3 className="font-display text-lg font-semibold text-white">
                  {plan.name}
                </h3>

                <div className="mt-3 flex items-baseline gap-1">
                  <span className="font-display text-4xl font-bold text-white">
                    {billing === "monthly"
                      ? plan.monthlyPrice
                      : plan.yearlyPrice}
                  </span>
                  {plan.monthlyPrice !== "Custom" && (
                    <span className="text-sm text-zinc-500">/mo</span>
                  )}
                </div>

                <div className="my-6 border-t border-zinc-800/70" />

                <ul className="space-y-3">
                  {plan.features.map((feature) => (
                    <li
                      key={feature.text}
                      className="flex items-start gap-2 text-sm"
                    >
                      {feature.included ? (
                        <Check
                          size={14}
                          className="mt-0.5 shrink-0 text-emerald-400"
                          aria-label="Included"
                        />
                      ) : (
                        <X
                          size={14}
                          className="mt-0.5 shrink-0 text-zinc-700"
                          aria-label="Not included"
                        />
                      )}
                      <span
                        className={
                          feature.included
                            ? "text-zinc-300"
                            : "text-zinc-600"
                        }
                      >
                        {feature.text}
                      </span>
                    </li>
                  ))}
                </ul>

                <a
                  href={plan.ctaHref}
                  className={cn(
                    "mt-7 inline-flex w-full items-center justify-center rounded-lg px-4 py-2.5 text-sm font-medium transition-all active:translate-y-[1px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50",
                    plan.popular
                      ? "bg-emerald-500 text-white hover:bg-emerald-600"
                      : "border border-zinc-700 text-zinc-200 hover:bg-zinc-800",
                  )}
                >
                  {plan.cta}
                </a>
                <p className="mt-3 text-center text-xs text-zinc-500">
                  {plan.riskReducer}
                </p>
              </div>
            </ScrollReveal>
          ))}
        </div>

        {/* Mini-FAQ */}
        <div className="mx-auto mt-20 max-w-3xl">
          <h3 className="mb-6 text-center font-display text-2xl font-bold text-white">
            Pricing questions
          </h3>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {faqs.map((faq) => (
              <div
                key={faq.q}
                className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5"
              >
                <h4 className="text-sm font-semibold text-white">{faq.q}</h4>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                  {faq.a}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
