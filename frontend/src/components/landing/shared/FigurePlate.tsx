"use client";

import { cn } from "@/lib/utils";

interface FigurePlateProps {
  /** "Plate I", "Fig. 3", etc. */
  index: string;
  /** Italic figure caption sitting beneath the visual. */
  caption: React.ReactNode;
  /** Optional sub-caption (e.g. attribution). */
  source?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

/** Editorial figure wrapper — renders a visualization inside a hairline
 *  paper frame and gives it a journal-style "Plate" caption beneath.
 *  Used by every engine row in the Five Engines section. */
export function FigurePlate({
  index,
  caption,
  source,
  children,
  className,
}: FigurePlateProps) {
  return (
    <figure className={cn("relative", className)}>
      <div className="relative rounded-sm border border-border-default bg-surface-card/70 px-5 py-7 sm:px-7 sm:py-9">
        <span
          aria-hidden="true"
          className="pointer-events-none absolute -top-px left-4 right-4 h-px bg-border-strong"
        />
        <span
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-px left-4 right-4 h-px bg-border-strong"
        />
        {children}
      </div>
      <figcaption className="mt-4 flex items-baseline gap-3 px-1">
        <span className="label-eyebrow shrink-0 text-fg-tertiary">{index}</span>
        <span className="editorial-italic flex-1 text-sm leading-snug text-fg-secondary">
          {caption}
        </span>
      </figcaption>
      {source && (
        <p className="mt-1 px-1 font-mono text-[10px] uppercase tracking-wider text-fg-tertiary">
          {source}
        </p>
      )}
    </figure>
  );
}
