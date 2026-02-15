"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";

const word = "AESTHETICA";

export function HeroSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const [scrollProgress, setScrollProgress] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      if (!sectionRef.current) return;
      
      const rect = sectionRef.current.getBoundingClientRect();
      const scrollableHeight = window.innerHeight * 2;
      const scrolled = -rect.top;
      const progress = Math.max(0, Math.min(1, scrolled / scrollableHeight));
      
      setScrollProgress(progress);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    
    return () => {
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);

  // Text fades out first (0 to 0.2)
  const textOpacity = Math.max(0, 1 - (scrollProgress / 0.2));
  
  // Image transforms start after text fades (0.2 to 1)
  const imageProgress = Math.max(0, Math.min(1, (scrollProgress - 0.2) / 0.8));
  
  // Keep the hero full-bleed without side imagery.
  const centerWidth = 100;
  const centerHeight = 100;
  const borderRadius = 0;
  const gap = 0;

  return (
    <section id="hero" ref={sectionRef} className="relative bg-background">
      {/* Sticky container for scroll animation */}
      <div className="sticky top-0 h-screen overflow-hidden">
        <div className="flex h-full w-full items-center justify-center">
          {/* Bento Grid Container */}
          <div 
            className="relative flex h-full w-full items-stretch justify-center"
            style={{ gap: `${gap}px` }}
          >

            {/* Main Hero Image - Center */}
            <div 
              className="relative overflow-hidden will-change-transform"
              style={{
                width: `${centerWidth}%`,
                height: `${centerHeight}%`,
                flex: "0 0 auto",
                borderRadius: `${borderRadius}px`,
              }}
            >
              {/* Text Behind - Fades out first */}
              <div 
                className="pointer-events-none absolute inset-0 z-20 flex items-start justify-center pt-8 md:pt-10"
                style={{ opacity: textOpacity }}
              >
                <h1
                  className="whitespace-nowrap font-black leading-[0.75] tracking-[-0.14em] text-black/80 mix-blend-multiply select-none"
                  style={{
                    // Big + blocky like the original hero, but sized to fit "AESTHETICA".
                    fontSize: 'clamp(96px, 18vw, 380px)',
                    transform: 'translateY(-6vh)',
                  }}
                >
                  {word.split("").map((letter, index) => (
                    <span
                      key={index}
                      className="inline-block animate-[slideUp_0.8s_ease-out_forwards] opacity-0"
                      style={{
                        animationDelay: `${index * 0.08}s`,
                        transition: 'all 1.5s',
                        transitionTimingFunction: 'cubic-bezier(0.86, 0, 0.07, 1)',
                      }}
                    >
                      {letter}
                    </span>
                  ))}
                </h1>
              </div>
              
              {/* Base video layer */}
              <video
                autoPlay
                loop
                muted
                playsInline
                preload="auto"
                className="absolute inset-0 z-10 h-full w-full object-cover"
              >
                <source src="/images/dress-one.mp4" type="video/mp4" />
              </video>

              {/* Foreground mask layer to keep the subject "in front" of the letters */}
              <video
                autoPlay
                loop
                muted
                playsInline
                preload="auto"
                aria-hidden="true"
                className="pointer-events-none absolute inset-0 z-30 h-full w-full object-cover"
                style={{
                  WebkitMaskImage:
                    'radial-gradient(circle at 50% 45%, rgba(0,0,0,1) 0%, rgba(0,0,0,1) 38%, rgba(0,0,0,0) 62%)',
                  maskImage:
                    'radial-gradient(circle at 50% 45%, rgba(0,0,0,1) 0%, rgba(0,0,0,1) 38%, rgba(0,0,0,0) 62%)',
                  WebkitMaskRepeat: 'no-repeat',
                  maskRepeat: 'no-repeat',
                  WebkitMaskSize: 'cover',
                  maskSize: 'cover',
                }}
              >
                <source src="/images/dress-one.mp4" type="video/mp4" />
              </video>
            </div>

          </div>
        </div>
      </div>

      {/* Tagline Section - Fixed at bottom */}
      <div 
        className="pointer-events-none fixed bottom-0 left-0 right-0 z-10 px-6 pb-12 md:px-12 md:pb-16 lg:px-20 lg:pb-20"
        style={{ opacity: textOpacity }}
      >
        <p className="mx-auto max-w-2xl text-center text-base leading-relaxed text-white italic md:text-lg lg:text-xl lg:leading-snug">
          One‑gesture capture
          <br />
          to matches + taste intelligence.
        </p>
      </div>

      {/* Scroll space to enable animation */}
      <div className="h-[200vh]" />
    </section>
  );
}
