import { Navbar } from "@/components/landing/Navbar";
import { HeroSection } from "@/components/landing/HeroSection";
import { ProblemSection } from "@/components/landing/ProblemSection";
import { HowItWorksSection } from "@/components/landing/HowItWorksSection";
import { ScannerPreview } from "@/components/landing/ScannerPreview";
import { FeaturesSection } from "@/components/landing/FeaturesSection";
import { AudienceSection } from "@/components/landing/AudienceSection";
import { DISARMSection } from "@/components/landing/DISARMSection";
import { EducationSection } from "@/components/landing/EducationSection";
import { PricingSection } from "@/components/landing/PricingSection";
import { CTASection } from "@/components/landing/CTASection";
import { Footer } from "@/components/landing/Footer";
import { FallingStars } from "@/components/landing/shared/FallingStars";

export default function LandingPage() {
  return (
    <>
      <div className="fixed inset-0 z-0 pointer-events-none">
        <FallingStars color="#10b981" count={180} />
      </div>
      <Navbar />
      <main className="relative z-10">
        <HeroSection />
        <ProblemSection />
        <HowItWorksSection />
        <ScannerPreview />
        <FeaturesSection />
        <AudienceSection />
        <DISARMSection />
        <EducationSection />
        <PricingSection />
        <CTASection />
      </main>
      <Footer />
    </>
  );
}
