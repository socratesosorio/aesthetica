"use client";

import { useEffect, useRef, useState } from "react";

const lines = ["You see it?", "You like it?", "You want it?", "You got it."] as const;

export function ConversionTextSection() {
  const sectionRef = useRef<HTMLElement | null>(null);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      if (!sectionRef.current) return;
      const el = sectionRef.current;
      const rect = el.getBoundingClientRect();
      const totalScrollable = Math.max(1, el.offsetHeight - window.innerHeight);
      const scrolled = -rect.top;
      setProgress(Math.max(0, Math.min(1, scrolled / totalScrollable)));
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const smoothstep = (t: number) => t * t * (3 - 2 * t);

  return (
    <section ref={sectionRef} className="relative bg-background">
      {/* Scroll space */}
      {/* Height is tuned to require scrolling through all 4 lines. */}
      <div className="relative h-[520vh]">
        {/* Sticky stage */}
        <div className="sticky top-0 flex h-screen items-center justify-center px-4 md:px-12 lg:px-20">
          <div className="relative w-full max-w-6xl">
            {lines.map((line, idx) => {
              const segment = 1 / lines.length;
              const start = idx * segment;
              const end = (idx + 1) * segment;
              const t = (progress - start) / segment;

              let opacity = 0;
              let translateY = 20;
              let blur = 18;

              if (t >= 0 && t <= 1) {
                if (t < 0.3) {
                  const a = smoothstep(t / 0.3);
                  opacity = a;
                  translateY = (1 - a) * 22;
                  blur = (1 - a) * 18;
                } else if (t > 0.7) {
                  const d = smoothstep((t - 0.7) / 0.3);
                  opacity = 1 - d;
                  translateY = -d * 18;
                  blur = d * 16;
                } else {
                  opacity = 1;
                  translateY = 0;
                  blur = 0;
                }
              }

              return (
                <div
                  key={line}
                  className="absolute inset-0 flex items-center justify-center"
                  style={{
                    opacity,
                    transform: `translate3d(0, ${translateY}px, 0)`,
                    filter: `blur(${blur}px)`,
                    willChange: "opacity, transform, filter",
                    transition: "opacity 220ms ease, transform 220ms ease, filter 220ms ease",
                  }}
                >
                  <div className="text-center font-semibold tracking-tight text-foreground text-4xl md:text-6xl lg:text-7xl">
                    {line}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

