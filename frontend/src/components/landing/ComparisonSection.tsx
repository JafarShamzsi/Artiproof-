"use client";

import { Check, Minus } from "lucide-react";

import { cn } from "@/lib/utils";
import { ChapterHeading } from "@/components/landing/shared/ChapterHeading";

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
          "tabular-nums font-mono text-[13px]",
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
        "mx-auto h-4 w-4",
        primary ? "text-brand-fg" : "text-fg-tertiary",
      )}
      strokeWidth={primary ? 2.25 : 1.5}
      aria-label="Yes"
    />
  ) : (
    <Minus
      className="mx-auto h-3 w-3 text-border-strong"
      strokeWidth={1.5}
      aria-label="No"
    />
  );
}

export function ComparisonSection() {
  return (
    <section id="compare" className="py-28 sm:py-32">
      <div className="mx-auto max-w-5xl px-6">
        <ChapterHeading
          numeral="IV"
          eyebrow="A comparative reading"
          title={
            <>
              Five integrity engines.{" "}
              <span className="italic text-brand-fg">One workflow. One bill.</span>
            </>
          }
          subtitle="The same submission, read five ways. Other tools each do one — you'd pay three of them and still miss the rings, the self-citation inflation, and the per-paragraph AI signal."
        />

        {/* Desktop / tablet — editorial spec table */}
        <div className="mt-16 hidden md:block">
          <div className="relative overflow-hidden">
            {/* Top doubled rule */}
            <hr className="rule-double" />

            <table className="w-full text-sm">
              <thead>
                <tr>
                  <th className="px-3 py-5 text-left">
                    <span className="label-eyebrow text-fg-tertiary">
                      Method
                    </span>
                  </th>
                  <th className="bg-brand-soft/40 px-3 py-5 text-center">
                    <div className="flex flex-col items-center gap-1">
                      <span className="font-display text-base font-semibold tracking-tight text-fg-primary">
                        ArtiProof
                      </span>
                      <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-brand-fg">
                        ◆ House finding
                      </span>
                    </div>
                  </th>
                  {COMPETITORS.map((c) => (
                    <th
                      key={c.key}
                      className="px-3 py-5 text-center"
                    >
                      <span className="font-display text-base font-medium text-fg-secondary">
                        {c.name}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colSpan={5}>
                    <hr className="rule-hair" />
                  </td>
                </tr>
                {features.map((row, idx) => (
                  <tr
                    key={row.name}
                    className={cn(
                      "border-b border-border-subtle transition-colors last:border-b-0",
                      idx % 2 === 0
                        ? "hover:bg-surface-card/60"
                        : "hover:bg-surface-card/60",
                    )}
                  >
                    <td className="px-3 py-4 align-middle">
                      <span className="inline-flex items-center gap-2.5">
                        <span className="font-mono text-[10px] tracking-wider text-fg-tertiary">
                          {String(idx + 1).padStart(2, "0")}
                        </span>
                        <span className="text-fg-primary">{row.name}</span>
                        {row.unique && (
                          <span className="inline-flex items-center rounded-sm border border-brand/30 bg-brand-soft px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.18em] text-brand-fg">
                            Only here
                          </span>
                        )}
                      </span>
                    </td>
                    <td className="bg-brand-soft/30 px-3 py-4 text-center">
                      <CellContent value={row.artiproof} primary />
                    </td>
                    <td className="px-3 py-4 text-center">
                      <CellContent value={row.turnitin} primary={false} />
                    </td>
                    <td className="px-3 py-4 text-center">
                      <CellContent value={row.gptzero} primary={false} />
                    </td>
                    <td className="px-3 py-4 text-center">
                      <CellContent value={row.originality} primary={false} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Bottom doubled rule */}
            <hr className="rule-double" />
          </div>

          {/* Footer caption — editorial italic */}
          <p className="editorial-italic mt-5 text-sm text-fg-tertiary">
            Comparison drawn from publicly listed feature pages and pricing
            tiers as of Spring 2026. Cross-checked against a mock submission
            run on each platform.
          </p>
        </div>

        {/* Mobile — summary cards + ArtiProof-only feature list. */}
        <div className="mt-12 md:hidden">
          <div className="space-y-3">
            <div className="rounded-sm border border-brand/40 bg-brand-soft p-5">
              <div className="flex items-center gap-2">
                <span className="font-display text-base font-semibold text-fg-primary">
                  ArtiProof
                </span>
                <span className="ml-auto font-mono text-sm tabular-nums text-brand-fg">
                  $20/mo
                </span>
              </div>
              <p className="editorial-italic mt-1.5 text-xs text-brand-fg">
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
                  className="rounded-sm border border-border-default bg-surface-card p-5"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-fg-primary">{c.name}</span>
                    {price && typeof price === "string" && (
                      <span className="ml-auto font-mono text-sm tabular-nums text-fg-secondary">
                        {price}
                      </span>
                    )}
                  </div>
                  <p className="editorial-italic mt-1.5 text-xs text-fg-tertiary">
                    {present} of {total} integrity features
                  </p>
                </div>
              );
            })}
          </div>

          <div className="mt-6 rounded-sm border border-border-default p-5">
            <span className="label-eyebrow text-brand-fg">
              Only on ArtiProof
            </span>
            <ul className="mt-4 space-y-2.5 text-sm text-fg-primary">
              {features
                .filter((f) => f.unique)
                .map((f) => (
                  <li key={f.name} className="flex items-center gap-2.5">
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
