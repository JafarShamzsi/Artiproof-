"use client";

import { useState } from "react";
import { Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { WavyBackground } from "./shared/WavyBackground";
import { SectionHeading } from "@/components/landing/shared/SectionHeading";
import { GlowCard } from "@/components/landing/shared/GlowCard";
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
    <section id="pricing" className="relative overflow-hidden py-24">
      <div className="absolute inset-0 z-0 opacity-40">
        <WavyBackground
          colors={["#064e3b", "#065f46", "#047857", "#059669", "#10b981"]}
          blur={15}
          speed="slow"
          waveOpacity={0.3}
          backgroundFill="#09090b"
        />
      </div>
      <div className="relative z-10 mx-auto max-w-7xl px-6">
        <SectionHeading
          eyebrow="PRICING"
          title="Choose Your Plan"
          gradient="Plan"
        />

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
            <ScrollReveal key={plan.name} delay={idx * 0.1}>
              <div className={cn("relative", plan.popular && "md:scale-105")}>
                {plan.popular && (
                  <>
                    {/* Glow halo behind the popular tier */}
                    <div
                      aria-hidden="true"
                      className="absolute -inset-px -z-10 rounded-2xl bg-gradient-to-br from-emerald-500/40 via-emerald-500/10 to-transparent blur-xl"
                    />
                    <div className="absolute left-1/2 top-0 z-20 -translate-x-1/2 -translate-y-1/2 whitespace-nowrap rounded-full bg-emerald-500 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-white shadow-lg shadow-emerald-500/40">
                      Most Popular
                    </div>
                  </>
                )}
                <GlowCard
                  className={cn(
                    "h-full p-8",
                    plan.popular && "ring-1 ring-emerald-500/40",
                  )}
                >
                  <h3 className="font-display text-xl font-bold text-white">
                    {plan.name}
                  </h3>

                  <div className="mt-4 flex items-baseline gap-1">
                    <span className="font-display text-4xl font-bold text-white">
                      {billing === "monthly"
                        ? plan.monthlyPrice
                        : plan.yearlyPrice}
                    </span>
                    {plan.monthlyPrice !== "Custom" && (
                      <span className="text-zinc-400">/mo</span>
                    )}
                  </div>

                  <div className="my-6 border-t border-zinc-800" />

                  <ul className="space-y-3">
                    {plan.features.map((feature) => (
                      <li
                        key={feature.text}
                        className="flex items-center gap-2 text-sm"
                      >
                        {feature.included ? (
                          <Check
                            size={16}
                            className="shrink-0 text-emerald-400"
                            aria-label="Included"
                          />
                        ) : (
                          <X
                            size={16}
                            className="shrink-0 text-zinc-600"
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
                      "mt-8 inline-flex w-full items-center justify-center rounded-lg px-4 py-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50",
                      plan.popular
                        ? "cta-glow bg-emerald-500 text-white shadow-lg shadow-emerald-500/20 hover:bg-emerald-600"
                        : "border border-zinc-700 text-zinc-300 hover:border-zinc-500 hover:text-white",
                    )}
                  >
                    {plan.cta}
                  </a>
                  <p className="mt-3 text-center text-xs text-zinc-500">
                    {plan.riskReducer}
                  </p>
                </GlowCard>
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
