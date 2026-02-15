"use client";

import { FadeImage } from "@/components/fade-image";

const tiles = [
  { image: "/images/outfit-1.png", span: "col-span-2 row-span-2" },
  { image: "/images/outfit-2.png", span: "col-span-1 row-span-1" },
  { image: "/images/outfit-3.png", span: "col-span-1 row-span-1" },
  { image: "/images/outfit-4.png", span: "col-span-1 row-span-2" },
  { image: "/images/outfit-5.png", span: "col-span-1 row-span-1" },
  { image: "/images/outfit-6.png", span: "col-span-2 row-span-1" },
  { image: "/images/outfit-7.png", span: "col-span-1 row-span-1" },
  { image: "/images/outfit-8.png", span: "col-span-1 row-span-2" },
  { image: "/images/outfit-9.png", span: "col-span-2 row-span-1" },
  { image: "/images/outfit-10.png", span: "col-span-1 row-span-1" },
];

export function OutfitGallerySection() {
  return (
    <section id="gallery" className="relative bg-background">
      <div className="grid w-full grid-cols-2 gap-2 auto-rows-[22vh] md:grid-cols-4 md:gap-3 md:auto-rows-[26vh] lg:gap-4 lg:auto-rows-[28vh]">
        {tiles.map((tile, index) => (
          <div
            key={tile.image}
            className={`relative overflow-hidden bg-secondary ${tile.span}`}
          >
            <FadeImage
              src={tile.image || "/placeholder.svg"}
              alt={`Outfit capture ${index + 1}`}
              fill
              className="object-cover"
            />
          </div>
        ))}
      </div>
    </section>
  );
}

