import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { PricingSection } from "@/components/landing/PricingSection";

export const metadata = {
  title: "Pricing — ArtiProof",
  description:
    "Four tiers — Free, Pro, Team, Institution. Transparent per-seat pricing for teams; flat monthly for individuals. No drip-pricing, no enterprise theater.",
};

/**
 * Dedicated pricing page so deep-links from the dashboard and from
 * partner sites land on a focused surface, not the busier landing
 * home. Reuses `<PricingSection>` verbatim — single source of truth
 * for the tiers, which means a price change on the landing also moves
 * here without an extra edit.
 *
 * The hash anchors (`#free`, `#pro`, `#team`, `#institution`) are
 * provided by the `PlanRow` `id` attribute and `scroll-mt-24` keeps
 * the anchor target below any future fixed header.
 */
export default function PricingPage() {
  return (
    <div className="bg-surface-base">
      <Navbar />
      <main id="main-content" className="pt-24">
        <PricingSection />
      </main>
      <Footer />
    </div>
  );
}
