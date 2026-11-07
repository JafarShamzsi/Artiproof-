"use client";

import { Check, Minus, Shield } from "lucide-react";

type Cell = boolean | string;

interface FeatureRow {
  name: string;
  artiproof: Cell;
  turnitin: Cell;
  gptzero: Cell;
  originality: Cell;
  /** True if no competitor in the table also has this feature. */
  unique?: boolean;
}

const features: FeatureRow[] = [
  { name: "Plagiarism detection",         artiproof: true,        turnitin: true,         gptzero: false,         originality: true       },
  { name: "AI content detection",         artiproof: true,        turnitin: true,         gptzero: true,          originality: true       },
  { name: "Citation ring detection",      artiproof: true,        turnitin: false,        gptzero: false,         originality: false,     unique: true },
  { name: "Researcher integrity scoring", artiproof: true,        turnitin: false,        gptzero: false,         originality: false,     unique: true },
  { name: "Fact-checking with sources",   artiproof: true,        turnitin: false,        gptzero: false,         originality: false,     unique: true },
  { name: "Self-citation analysis",       artiproof: true,        turnitin: false,        gptzero: false,         originality: false,     unique: true },
  { name: "Free tier",                    artiproof: true,        turnitin: false,        gptzero: true,          originality: false      },
  { name: "Starting price",               artiproof: "$20/mo",    turnitin: "$3/student", gptzero: "$15/mo",      originality: "$15/mo"   },
];

const COMPETITORS = [
  { key: "turnitin" as const, name: "Turnitin" },
  { key: "gptzero" as const, name: "GPTZero" },
  { key: "originality" as const, name: "Originality" },
];

function CellContent({ value, primary }: { value: Cell; primary: boolean }) {
  if (typeof value === "string") {
    return (
      <span
        className={
          "tabular-nums " +
          (primary ? "font-semibold text-white" : "text-zinc-400")
        }
      >
        {value}
      </span>
    );
  }
  return value ? (
    <Check
      className={
        "mx-auto h-5 w-5 " + (primary ? "text-emerald-400" : "text-zinc-500")
      }
      strokeWidth={primary ? 2 : 1.5}
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
          <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-balance text-white sm:text-4xl">
            Five integrity engines. One workflow. One bill.
          </h2>
        </div>

        {/* Desktop / tablet — full feature table */}
        <div className="hidden overflow-x-auto md:block">
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
                  className="border-b border-zinc-800/60 transition-colors last:border-b-0 hover:bg-white/[0.02]"
                >
                  <td className="px-4 py-3 text-zinc-300">
                    <span className="inline-flex items-center gap-2">
                      {row.name}
                      {row.unique && (
                        <span className="inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-emerald-300">
                          Unique
                        </span>
                      )}
                    </span>
                  </td>
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

        {/* Mobile — summary cards + ArtiProof-only feature list. The full
            table doesn't survive a 360px viewport without horizontal scroll
            and tiny text, so we summarize per-competitor instead. */}
        <div className="md:hidden">
          <div className="space-y-3">
            <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/[0.04] p-4">
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-emerald-400" aria-hidden="true" />
                <span className="font-semibold text-white">ArtiProof</span>
                <span className="ml-auto tabular-nums text-sm text-zinc-400">
                  $20/mo
                </span>
              </div>
              <p className="mt-1 text-xs text-emerald-300/80">
                7 of 7 integrity features
              </p>
            </div>

            {COMPETITORS.map((c) => {
              const present = features.filter(
                (f) => typeof f[c.key] === "boolean" && f[c.key] === true,
              ).length;
              const total = features.filter(
                (f) => typeof f[c.key] === "boolean",
              ).length;
              const price = features.find((f) => f.name === "Starting price")?.[c.key];
              return (
                <div
                  key={c.key}
                  className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-zinc-200">{c.name}</span>
                    {price && typeof price === "string" && (
                      <span className="ml-auto tabular-nums text-sm text-zinc-500">
                        {price}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-zinc-500">
                    {present} of {total} integrity features
                  </p>
                </div>
              );
            })}
          </div>

          <div className="mt-6 rounded-xl border border-zinc-800 p-4">
            <p className="text-xs font-medium uppercase tracking-wider text-emerald-400">
              Only on ArtiProof
            </p>
            <ul className="mt-3 space-y-2 text-sm text-zinc-300">
              {features
                .filter((f) => f.unique)
                .map((f) => (
                  <li key={f.name} className="flex items-center gap-2">
                    <Check
                      className="h-4 w-4 shrink-0 text-emerald-400"
                      strokeWidth={2}
                      aria-hidden="true"
                    />
                    {f.name}
                  </li>
                ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
