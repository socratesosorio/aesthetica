"use client";

export function FeaturedProductsSection() {
  return (
    <section id="glasses" className="relative bg-black">
      <div className="relative h-[100svh] w-full overflow-hidden">
        <video
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          className="animate-fade-in absolute inset-0 h-full w-full object-cover"
        >
          <source src="/images/mrb.mp4" type="video/mp4" />
        </video>
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/15 via-transparent to-black/20" />
      </div>
    </section>
  );
}
