import { Header } from "@/components/header";
import { HeroSection } from "@/components/sections/hero-section";
import { PhilosophySection } from "@/components/sections/philosophy-section";
import { FeaturedProductsSection } from "@/components/sections/featured-products-section";
import { ConversionTextSection } from "@/components/sections/conversion-text-section";
import { TechnologySection } from "@/components/sections/technology-section";
import { OutfitGallerySection } from "@/components/sections/outfit-gallery-section";
import { EditorialSection } from "@/components/sections/editorial-section";
import { TestimonialsSection } from "@/components/sections/testimonials-section";
import { FooterSection } from "@/components/sections/footer-section";

export default function Home() {
  return (
    <main className="min-h-screen bg-background">
      <Header />
      <HeroSection />
      <PhilosophySection />
      <FeaturedProductsSection />
      <ConversionTextSection />
      <OutfitGallerySection />
      <TechnologySection />
      <EditorialSection />
      <TestimonialsSection />
      <FooterSection />
    </main>
  );
}
