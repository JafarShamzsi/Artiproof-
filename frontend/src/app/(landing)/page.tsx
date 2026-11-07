import { Navbar } from "@/components/landing/Navbar";
import { HeroSection } from "@/components/landing/HeroSection";
import { TrustSection } from "@/components/landing/TrustSection";
import { ScannerPreview } from "@/components/landing/ScannerPreview";
import { ComparisonSection } from "@/components/landing/ComparisonSection";
import { FeaturesSection } from "@/components/landing/FeaturesSection";
import { PricingSection } from "@/components/landing/PricingSection";
import { CTASection } from "@/components/landing/CTASection";
import { Footer } from "@/components/landing/Footer";

const SectionDivider = () => (
  <div
    aria-hidden="true"
    className="h-px bg-gradient-to-r from-transparent via-border-default to-transparent"
  />
);

export default function LandingPage() {
  return (
    <>
      <Navbar />
      <main id="main-content" tabIndex={-1} className="relative z-10">
        <HeroSection />
        <SectionDivider />
        <TrustSection />
        <SectionDivider />
        <ScannerPreview />
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
