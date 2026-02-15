"use client";

export function TestimonialsSection() {
  return (
    <section id="about" className="bg-background">
      {/* About Video with Text Overlay */}
      <div className="relative aspect-[16/9] w-full">
        <video
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          className="absolute inset-0 h-full w-full object-cover"
        >
          <source src="/images/dress-glow.mp4" type="video/mp4" />
        </video>
        {/* Fade gradient overlay - dark at bottom fading to transparent at top */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/30 to-transparent" />
        
        {/* Text Overlay */}
        <div className="absolute inset-0 flex items-end justify-center px-6 pb-16 md:px-12 md:pb-24 lg:px-20 lg:pb-32">
          <p className="mx-auto max-w-5xl text-2xl leading-relaxed text-white md:text-3xl lg:text-[2.5rem] lg:leading-snug text-center">
            A spatial fashion system that captures real‑world inspiration and converts it into structure —
            matched products, interpretable taste signals, and a profile that evolves with you.
          </p>
        </div>
      </div>
    </section>
  );
}
