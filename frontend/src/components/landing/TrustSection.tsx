"use client";

const institutions = [
  "ADA University",
  "Baku State University",
  "Khazar University",
  "ASOIU",
  "Azerbaijan Medical University",
  "UNEC",
];

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
    <section className="border-y border-zinc-800/50 py-12">
      <div className="mx-auto max-w-6xl px-6">
        {/* Logo / institution strip */}
        <p className="text-center text-xs uppercase tracking-wider text-zinc-500">
          Targeting researchers across
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 opacity-50 transition-opacity hover:opacity-80 md:gap-x-12">
          {institutions.map((name) => (
            <span
              key={name}
              className="whitespace-nowrap text-sm font-medium text-zinc-400"
            >
              {name}
            </span>
          ))}
        </div>

        {/* Stats bar */}
        <div className="mt-12 grid grid-cols-2 gap-8 border-t border-zinc-800/50 pt-8 md:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.label} className="text-center">
              <div className="font-display text-3xl font-bold text-white">
                {stat.value}
              </div>
              <div className="mt-1 text-sm text-zinc-400">{stat.label}</div>
              <div className="mt-0.5 text-[10px] text-zinc-600">
                Source: {stat.source}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
