"use client";

const stats = [
  {
    value: "14,000+",
    label: "Retractions detected annually",
    source: "Retraction Watch",
  },
  {
    value: "92%",
    label: "Students using AI tools",
    source: "HEPI Survey 2024",
  },
  {
    value: "$392K",
    label: "Cost per retracted paper",
    source: "eLife (2024)",
  },
  {
    value: "< 2 min",
    label: "Average analysis time",
    source: "ArtiProof telemetry",
  },
];

export function TrustSection() {
  return (
    <section className="py-16">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid grid-cols-2 gap-x-8 gap-y-10 md:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.label}>
              <div className="font-display text-3xl font-bold text-white md:text-4xl">
                {stat.value}
              </div>
              <div className="mt-1 text-sm leading-snug text-zinc-400">
                {stat.label}
              </div>
              <div className="mt-1 text-[11px] text-zinc-600">
                Source: {stat.source}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
