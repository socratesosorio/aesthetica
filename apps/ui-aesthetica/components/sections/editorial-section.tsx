"use client";

const specs = [
  { label: "End‑to‑end latency", value: "<5s" },
  { label: "Embedding retrieval", value: "<300ms" },
  { label: "Vector search", value: "<200ms" },
  { label: "Radar update", value: "<50ms" },
];

export function EditorialSection() {
  return (
    <section className="bg-background">
      <div className="grid grid-cols-2 border-t border-border md:grid-cols-4">
        {specs.map((spec) => (
          <div
            key={spec.label}
            className="group border-b border-r border-border p-10 text-center last:border-r-0 md:border-b-0 md:p-14"
          >
            <p className="mb-3 text-xs uppercase tracking-widest text-muted-foreground">
              {spec.label}
            </p>
            <p className="font-semibold text-foreground text-5xl md:text-6xl transition-transform duration-300 group-hover:scale-[1.02]">
              {spec.value}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
