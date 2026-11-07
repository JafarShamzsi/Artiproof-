"use client";

import { Check, X } from "lucide-react";
import { ScrollReveal } from "./shared/ScrollReveal";
import { SectionHeading } from "./shared/SectionHeading";

type Cell = boolean | string;

interface FeatureRow {
  name: string;
  artiproof: Cell;
  turnitin: Cell;
  gptzero: Cell;
  originality: Cell;
}

const features: FeatureRow[] = [
  { name: "Plagiarism Detection",         artiproof: true,        turnitin: true,         gptzero: false,         originality: true       },
  { name: "AI Content Detection",         artiproof: true,        turnitin: true,         gptzero: true,          originality: true       },
  { name: "Citation Ring Detection",      artiproof: true,        turnitin: false,        gptzero: false,         originality: false      },
  { name: "Researcher Integrity Scoring", artiproof: true,        turnitin: false,        gptzero: false,         originality: false      },
  { name: "Fact-Checking with Sources",   artiproof: true,        turnitin: false,        gptzero: false,         originality: false      },
  { name: "Self-Citation Analysis",       artiproof: true,        turnitin: false,        gptzero: false,         originality: false      },
  { name: "Free Tier",                    artiproof: true,        turnitin: false,        gptzero: true,          originality: false      },
  { name: "Starting Price",               artiproof: "$20/mo",    turnitin: "$3/student", gptzero: "$15/mo",      originality: "$15/mo"   },
];

function CellContent({ value }: { value: Cell }) {
  if (typeof value === "string") {
    return <span className="text-zinc-300">{value}</span>;
  }
  return value ? (
    <Check className="mx-auto h-5 w-5 text-emerald-400" aria-label="Yes" />
  ) : (
    <X className="mx-auto h-5 w-5 text-zinc-700" aria-label="No" />
  );
}

export function ComparisonSection() {
  return (
    <section className="py-24 md:py-32">
      <div className="mx-auto max-w-5xl px-6">
        <SectionHeading
          eyebrow="HOW WE COMPARE"
          title="More Features, Better Price"
          gradient="Price"
        />
        <ScrollReveal>
          <div className="overflow-x-auto rounded-xl border border-zinc-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/40">
                  <th className="px-4 py-3 text-left font-medium text-zinc-400">
                    Feature
                  </th>
                  <th className="px-4 py-3 text-center font-semibold text-emerald-400">
                    <span className="inline-flex items-center gap-1.5">
                      ArtiProof
                    </span>
                  </th>
                  <th className="px-4 py-3 text-center font-medium text-zinc-400">
                    Turnitin
                  </th>
                  <th className="px-4 py-3 text-center font-medium text-zinc-400">
                    GPTZero
                  </th>
                  <th className="px-4 py-3 text-center font-medium text-zinc-400">
                    Originality
                  </th>
                </tr>
              </thead>
              <tbody>
                {features.map((row, i) => (
                  <tr
                    key={row.name}
                    className={i % 2 === 0 ? "bg-transparent" : "bg-zinc-900/30"}
                  >
                    <td className="px-4 py-3 font-medium text-white">
                      {row.name}
                    </td>
                    <td className="border-x border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-center">
                      <CellContent value={row.artiproof} />
                    </td>
                    <td className="px-4 py-3 text-center text-zinc-400">
                      <CellContent value={row.turnitin} />
                    </td>
                    <td className="px-4 py-3 text-center text-zinc-400">
                      <CellContent value={row.gptzero} />
                    </td>
                    <td className="px-4 py-3 text-center text-zinc-400">
                      <CellContent value={row.originality} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-center text-xs text-zinc-500">
            Five integrity engines in one workflow — pricing accurate as of
            launch.
          </p>
        </ScrollReveal>
      </div>
    </section>
  );
}
