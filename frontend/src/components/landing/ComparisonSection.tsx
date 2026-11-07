"use client";

import { Check, Minus, Shield } from "lucide-react";

type Cell = boolean | string;

interface FeatureRow {
  name: string;
  artiproof: Cell;
  turnitin: Cell;
  gptzero: Cell;
  originality: Cell;
}

const features: FeatureRow[] = [
  { name: "Plagiarism detection",         artiproof: true,        turnitin: true,         gptzero: false,         originality: true       },
  { name: "AI content detection",         artiproof: true,        turnitin: true,         gptzero: true,          originality: true       },
  { name: "Citation ring detection",      artiproof: true,        turnitin: false,        gptzero: false,         originality: false      },
  { name: "Researcher integrity scoring", artiproof: true,        turnitin: false,        gptzero: false,         originality: false      },
  { name: "Fact-checking with sources",   artiproof: true,        turnitin: false,        gptzero: false,         originality: false      },
  { name: "Self-citation analysis",       artiproof: true,        turnitin: false,        gptzero: false,         originality: false      },
  { name: "Free tier",                    artiproof: true,        turnitin: false,        gptzero: true,          originality: false      },
  { name: "Starting price",               artiproof: "$20/mo",    turnitin: "$3/student", gptzero: "$15/mo",      originality: "$15/mo"   },
];

function CellContent({ value, primary }: { value: Cell; primary: boolean }) {
  if (typeof value === "string") {
    return (
      <span className={primary ? "font-semibold text-white" : "text-zinc-400"}>
        {value}
      </span>
    );
  }
  return value ? (
    <Check
      className={
        "mx-auto h-4 w-4 " + (primary ? "text-emerald-400" : "text-zinc-500")
      }
      aria-label="Yes"
    />
  ) : (
    <Minus className="mx-auto h-4 w-4 text-zinc-700" aria-label="No" />
  );
}

export function ComparisonSection() {
  return (
    <section className="py-24">
      <div className="mx-auto max-w-5xl px-6">
        <div className="mb-12 max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">
            How we compare
          </p>
          <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Five integrity engines. One workflow. One bill.
          </h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="px-4 py-3 text-left font-medium text-zinc-500">
                  Feature
                </th>
                <th className="px-4 py-3 text-center">
                  <span className="inline-flex items-center gap-1.5 font-semibold text-white">
                    <Shield className="h-3.5 w-3.5 text-emerald-400" aria-hidden="true" />
                    ArtiProof
                  </span>
                </th>
                <th className="px-4 py-3 text-center font-medium text-zinc-500">
                  Turnitin
                </th>
                <th className="px-4 py-3 text-center font-medium text-zinc-500">
                  GPTZero
                </th>
                <th className="px-4 py-3 text-center font-medium text-zinc-500">
                  Originality
                </th>
              </tr>
            </thead>
            <tbody>
              {features.map((row) => (
                <tr
                  key={row.name}
                  className="border-b border-zinc-800/60 last:border-b-0"
                >
                  <td className="px-4 py-3 text-zinc-300">{row.name}</td>
                  <td className="px-4 py-3 text-center">
                    <CellContent value={row.artiproof} primary />
                  </td>
                  <td className="px-4 py-3 text-center">
                    <CellContent value={row.turnitin} primary={false} />
                  </td>
                  <td className="px-4 py-3 text-center">
                    <CellContent value={row.gptzero} primary={false} />
                  </td>
                  <td className="px-4 py-3 text-center">
                    <CellContent value={row.originality} primary={false} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
