"use client";

import { Check, Minus } from "lucide-react";

type Cell = boolean | string;

interface FeatureRow {
  name: string;
  artiproof: Cell;
  turnitin: Cell;
  gptzero: Cell;
  originality: Cell;
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
        className={cn(
          "tabular-nums",
          primary ? "font-semibold text-fg-primary" : "text-fg-secondary",
        )}
      >
        {value}
      </span>
    );
  }
  return value ? (
    <Check
      className={cn(
        "mx-auto h-5 w-5",
        primary ? "text-brand-fg" : "text-fg-tertiary",
      )}
      strokeWidth={primary ? 2 : 1.5}
      aria-label="Yes"
    />
  ) : (
    <Minus className="mx-auto h-4 w-4 text-border-strong" strokeWidth={1.5} aria-label="No" />
  );
}

import { cn } from "@/lib/utils";

export function ComparisonSection() {
  return (
    <section id="compare" className="py-24 sm:py-28">
      <div className="mx-auto max-w-5xl px-6">
        <div className="mb-12 max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-fg-tertiary">
            How we compare
          </p>
          <h2 className="mt-3 font-display text-4xl font-semibold leading-[1.05] tracking-tight text-balance text-fg-primary sm:text-5xl">
            Five integrity engines.{" "}
            <span className="italic text-brand-fg">One workflow. One bill.</span>
          </h2>
        </div>

        {/* Desktop / tablet — full feature table */}
        <div className="hidden overflow-x-auto rounded-xl border border-border-default md:block">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-default bg-surface-card">
                <th className="px-4 py-3.5 text-left font-medium text-fg-tertiary">
                  Feature
                </th>
                <th className="px-4 py-3.5 text-center">
                  <span className="font-display font-semibold text-fg-primary">
                    ArtiProof
                  </span>
                </th>
                <th className="px-4 py-3.5 text-center font-medium text-fg-tertiary">
                  Turnitin
                </th>
                <th className="px-4 py-3.5 text-center font-medium text-fg-tertiary">
                  GPTZero
                </th>
                <th className="px-4 py-3.5 text-center font-medium text-fg-tertiary">
                  Originality
                </th>
              </tr>
            </thead>
            <tbody>
              {features.map((row) => (
                <tr
                  key={row.name}
                  className="border-b border-border-subtle transition-colors last:border-b-0 hover:bg-surface-card"
                >
                  <td className="px-4 py-3.5 text-fg-primary">
                    <span className="inline-flex items-center gap-2">
                      {row.name}
                      {row.unique && (
                        <span className="inline-flex items-center rounded-full border border-brand/30 bg-brand-soft px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-brand-fg">
                          Only here
                        </span>
                      )}
                    </span>
                  </td>
                  <td className="px-4 py-3.5 text-center">
                    <CellContent value={row.artiproof} primary />
                  </td>
                  <td className="px-4 py-3.5 text-center">
                    <CellContent value={row.turnitin} primary={false} />
                  </td>
                  <td className="px-4 py-3.5 text-center">
                    <CellContent value={row.gptzero} primary={false} />
                  </td>
                  <td className="px-4 py-3.5 text-center">
                    <CellContent value={row.originality} primary={false} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile — summary cards + ArtiProof-only feature list. */}
        <div className="md:hidden">
          <div className="space-y-3">
            <div className="rounded-xl border border-brand/40 bg-brand-soft p-4">
              <div className="flex items-center gap-2">
                <span className="font-display font-semibold text-fg-primary">
                  ArtiProof
                </span>
                <span className="ml-auto tabular-nums text-sm text-brand-fg">
                  $20/mo
                </span>
              </div>
              <p className="mt-1 text-xs text-brand-fg">
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
                  className="rounded-xl border border-border-default bg-surface-card p-4"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-fg-primary">{c.name}</span>
                    {price && typeof price === "string" && (
                      <span className="ml-auto tabular-nums text-sm text-fg-secondary">
                        {price}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-fg-tertiary">
                    {present} of {total} integrity features
                  </p>
                </div>
              );
            })}
          </div>

          <div className="mt-6 rounded-xl border border-border-default p-4">
            <p className="text-xs font-medium uppercase tracking-wider text-brand-fg">
              Only on ArtiProof
            </p>
            <ul className="mt-3 space-y-2 text-sm text-fg-primary">
              {features
                .filter((f) => f.unique)
                .map((f) => (
                  <li key={f.name} className="flex items-center gap-2">
                    <Check
                      className="h-4 w-4 shrink-0 text-brand-fg"
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
