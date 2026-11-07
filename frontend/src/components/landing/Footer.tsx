const productLinks = [
  { label: "Source verification", href: "/#features" },
  { label: "Claim analysis", href: "/#features" },
  { label: "AI detection", href: "/#features" },
  { label: "Citation rings", href: "/#features" },
  { label: "Researcher integrity", href: "/#features" },
];

const navigationLinks = [
  { label: "How it works", href: "/#how-it-works" },
  { label: "Compare", href: "/#compare" },
  { label: "Pricing", href: "/#pricing" },
  { label: "Contact", href: "mailto:info@example.invalid" },
];

const legalLinks = [
  { label: "Privacy", href: "/privacy" },
  { label: "Terms", href: "/terms" },
];

function BrandMark() {
  return (
    <span
      aria-hidden="true"
      className="relative inline-flex h-8 w-8 items-center justify-center rounded-full border border-border-strong bg-surface-base font-display text-[15px] font-semibold leading-none text-brand"
    >
      A
      <span
        aria-hidden="true"
        className="absolute inset-0.5 rounded-full border border-border-default"
      />
    </span>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-border-strong bg-surface-card">
      {/* Top doubled rule — signals the colophon. */}
      <div className="border-b border-border-default">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-6 py-3">
          <span className="label-eyebrow text-fg-tertiary">Colophon</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-fg-tertiary">
            ArtiProof · Spring 2026
          </span>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-6 py-16">
        <div className="grid grid-cols-2 gap-x-10 gap-y-12 md:grid-cols-[2fr_1fr_1fr_1fr]">
          {/* Wordmark + colophon copy */}
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-3">
              <BrandMark />
              <span className="font-display text-xl font-semibold tracking-tight text-fg-primary">
                ArtiProof
              </span>
            </div>
            <p className="editorial-italic mt-5 max-w-sm text-base leading-relaxed text-fg-secondary">
              Set in Fraunces and Newsreader. Research integrity, made
              auditable. Built for universities across Azerbaijan and
              the Eastern Partnership region.
            </p>
            <p className="mt-6 font-mono text-[10px] uppercase tracking-[0.2em] text-fg-tertiary">
              Made in Baku · pre-launch
            </p>
          </div>

          <div>
            <span className="label-eyebrow text-fg-tertiary">
              The engines
            </span>
            <ul className="mt-4 space-y-2.5">
              {productLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-fg-secondary transition-colors hover:text-brand-fg"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <span className="label-eyebrow text-fg-tertiary">
              The pages
            </span>
            <ul className="mt-4 space-y-2.5">
              {navigationLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-fg-secondary transition-colors hover:text-brand-fg"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <span className="label-eyebrow text-fg-tertiary">
              The fine print
            </span>
            <ul className="mt-4 space-y-2.5">
              {legalLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-fg-secondary transition-colors hover:text-brand-fg"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-14 flex flex-wrap items-baseline justify-between gap-3 border-t border-border-subtle pt-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-fg-tertiary">
            © 2026 ArtiProof — All findings reserved.
          </p>
          <p className="editorial-italic text-sm text-fg-tertiary">
            Research integrity, made transparent.
          </p>
        </div>
      </div>
    </footer>
  );
}
