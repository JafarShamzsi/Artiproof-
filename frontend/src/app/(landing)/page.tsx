import { Navbar } from "@/components/landing/Navbar";
import { HeroSection } from "@/components/landing/HeroSection";
import { ProblemSection } from "@/components/landing/ProblemSection";
import { TrustSection } from "@/components/landing/TrustSection";
import { ComparisonSection } from "@/components/landing/ComparisonSection";
import { HowItWorksSection } from "@/components/landing/HowItWorksSection";
import { ScannerPreview } from "@/components/landing/ScannerPreview";
import { FeaturesSection } from "@/components/landing/FeaturesSection";
import { AudienceSection } from "@/components/landing/AudienceSection";
import { PricingSection } from "@/components/landing/PricingSection";
import { CTASection } from "@/components/landing/CTASection";
import { Footer } from "@/components/landing/Footer";
import { FadeIn } from "@/components/ui/fade-in";

const SectionDivider = () => (
  <div
    aria-hidden="true"
    className="h-px bg-gradient-to-r from-transparent via-zinc-800 to-transparent"
  />
);

export default function LandingPage() {
  return (
    <>
      {/* Gradient mesh + grid backdrop — fixed, behind everything else. */}
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute left-1/4 top-0 h-96 w-96 rounded-full bg-emerald-500/5 blur-[128px]" />
        <div className="absolute right-1/4 top-1/3 h-96 w-96 rounded-full bg-blue-500/5 blur-[128px]" />
        <div className="absolute bottom-1/3 left-1/3 h-96 w-96 rounded-full bg-purple-500/5 blur-[128px]" />
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:64px_64px]" />
      </div>

      <Navbar />
      <main id="main-content" tabIndex={-1} className="relative z-10">
        <HeroSection />
        <SectionDivider />
        <FadeIn>
          <TrustSection />
        </FadeIn>
        <SectionDivider />
        <FadeIn delay={0.05}>
          <ProblemSection />
        </FadeIn>
        <SectionDivider />
        <FadeIn delay={0.05}>
          <HowItWorksSection />
        </FadeIn>
        <SectionDivider />
        <FadeIn delay={0.05}>
          <ScannerPreview />
        </FadeIn>
        <SectionDivider />
        <FadeIn delay={0.05}>
          <FeaturesSection />
        </FadeIn>
        <SectionDivider />
        <FadeIn delay={0.05}>
          <ComparisonSection />
        </FadeIn>
        <SectionDivider />
        <FadeIn delay={0.05}>
          <AudienceSection />
        </FadeIn>
        <SectionDivider />
        <FadeIn delay={0.05}>
          <PricingSection />
        </FadeIn>
        <SectionDivider />
        <FadeIn delay={0.05}>
          <CTASection />
        </FadeIn>
      </main>
      <Footer />
    </>
  );
}
