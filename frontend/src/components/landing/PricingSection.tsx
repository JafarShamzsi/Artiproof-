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
  popular?: boolean;
}

const plans: PricingPlan[] = [
  {
    name: "Free",
    monthlyPrice: "$0",
    yearlyPrice: "$0",
    features: [
      { text: "10 scans per day", included: true },
      { text: "Basic threat score", included: true },
      { text: "Education hub access", included: true },
      { text: "Community participation", included: true },
      { text: "Detailed engine results", included: false },
      { text: "DISARM classification", included: false },
      { text: "Export reports", included: false },
      { text: "API access", included: false },
    ],
    cta: "Get Started",
  },
  {
    name: "Pro",
    monthlyPrice: "$12",
    yearlyPrice: "$8",
    popular: true,
    features: [
      { text: "Unlimited scans", included: true },
      { text: "Full engine results", included: true },
      { text: "DISARM classification", included: true },
      { text: "Analytics dashboard", included: true },
      { text: "Export PDF & CSV", included: true },
      { text: "Bulk scanning", included: true },
      { text: "Custom alerts", included: true },
      { text: "Priority processing", included: true },
      { text: "API access", included: false },
      { text: "Team management", included: false },
    ],
    cta: "Start Pro",
  },
  {
    name: "Enterprise",
    monthlyPrice: "Custom",
    yearlyPrice: "Custom",
    features: [
      { text: "Everything in Pro", included: true },
      { text: "Unlimited bulk scanning", included: true },
      { text: "API access", included: true },
      { text: "Team management", included: true },
      { text: "Webhook integrations", included: true },
      { text: "White-label reports", included: true },
      { text: "Dedicated support", included: true },
      { text: "Custom SLA", included: true },
    ],
    cta: "Contact Sales",
  },
];

export function PricingSection() {
  const [billing, setBilling] = useState<BillingPeriod>("monthly");

  return (
    <section id="pricing" className="relative py-24 overflow-hidden">
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
          title="Choose Your Shield"
          gradient="Shield"
        />

        {/* Billing Toggle */}
        <div className="mb-12 flex items-center justify-center gap-1">
          <div className="inline-flex rounded-full border border-zinc-800 bg-zinc-900 p-1">
            <button
              onClick={() => setBilling("monthly")}
              className={cn(
                "rounded-full px-4 py-2 text-sm font-medium transition-colors",
                billing === "monthly"
                  ? "bg-white/10 text-white"
                  : "text-zinc-400 hover:text-zinc-300"
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
                  : "text-zinc-400 hover:text-zinc-300"
              )}
            >
              Yearly (Save 30%)
            </button>
          </div>
        </div>

        {/* Pricing Cards */}
        <div className="mx-auto grid max-w-5xl grid-cols-1 gap-6 md:grid-cols-3">
          {plans.map((plan, idx) => (
            <ScrollReveal key={plan.name} delay={idx * 0.1}>
              <div
                className={cn(
                  "relative",
                  plan.popular && "md:scale-105"
                )}
              >
                {plan.popular && (
                  <div className="absolute left-1/2 top-0 z-20 -translate-x-1/2 -translate-y-1/2 whitespace-nowrap rounded-full bg-emerald-500 px-3 py-1 text-xs font-medium text-white">
                    Most Popular
                  </div>
                )}
                <GlowCard
                  className={cn(
                    "p-8",
                    plan.popular && "ring-1 ring-emerald-500/20"
                  )}
                >
                  <h3 className="text-xl font-bold text-white">{plan.name}</h3>

                  <div className="mt-4 flex items-baseline gap-1">
                    <span className="text-4xl font-bold text-white">
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
                          <Check size={16} className="shrink-0 text-emerald-400" />
                        ) : (
                          <X size={16} className="shrink-0 text-zinc-600" />
                        )}
                        <span
                          className={
                            feature.included ? "text-zinc-300" : "text-zinc-600"
                          }
                        >
                          {feature.text}
                        </span>
                      </li>
                    ))}
                  </ul>

                  <button
                    className={cn(
                      "mt-8 w-full rounded-lg px-4 py-3 text-sm font-medium transition-colors",
                      plan.popular
                        ? "bg-emerald-500 text-white hover:bg-emerald-600"
                        : "border border-zinc-700 text-zinc-300 hover:border-zinc-500 hover:text-white"
                    )}
                  >
                    {plan.cta}
                  </button>
                </GlowCard>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}
