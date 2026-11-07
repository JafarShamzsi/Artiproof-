import { Navbar } from "@/components/landing/Navbar";
import { HeroSection } from "@/components/landing/HeroSection";
import { ScannerPreview } from "@/components/landing/ScannerPreview";
import { TrustSection } from "@/components/landing/TrustSection";
import { ComparisonSection } from "@/components/landing/ComparisonSection";
import { FeaturesSection } from "@/components/landing/FeaturesSection";
import { PricingSection } from "@/components/landing/PricingSection";
import { CTASection } from "@/components/landing/CTASection";
import { Footer } from "@/components/landing/Footer";

const SectionDivider = () => (
  <div
    aria-hidden="true"
    className="h-px bg-gradient-to-r from-transparent via-zinc-800 to-transparent"
  />
);

export default function LandingPage() {
  return (
    <>
      {/* Single subtle emerald glow, off-center, behind everything.
          Replaces the previous 3-color gradient mesh + grid pattern stack. */}
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute left-1/2 top-[-20%] h-[60vh] w-[60vh] -translate-x-1/2 rounded-full bg-emerald-500/[0.04] blur-[140px]" />
      </div>

      <Navbar />
      <main id="main-content" tabIndex={-1} className="relative z-10">
        <HeroSection />
        <SectionDivider />
        <ScannerPreview />
        <SectionDivider />
        <TrustSection />
        <SectionDivider />
        <ComparisonSection />
        <SectionDivider />
        <FeaturesSection />
        <SectionDivider />
        <PricingSection />
        <CTASection />
      </main>
      <Footer />
    </>
  );
}
