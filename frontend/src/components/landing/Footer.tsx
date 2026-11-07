const productLinks = [
  { label: "Source verification", href: "/#features" },
  { label: "AI detection", href: "/#features" },
  { label: "Citation analysis", href: "/#features" },
  { label: "Pricing", href: "/#pricing" },
];

const companyLinks = [
  { label: "How it works", href: "/#how-it-works" },
  { label: "Compare", href: "/#compare" },
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
      className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-brand font-display text-[11px] font-bold leading-none text-white"
    >
      A
    </span>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-border-default bg-surface-card">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <div className="grid grid-cols-2 gap-10 md:grid-cols-4">
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-2.5">
              <BrandMark />
              <span className="font-display text-base font-semibold tracking-tight text-fg-primary">
                ArtiProof
              </span>
            </div>
            <p className="mt-3 max-w-xs text-sm leading-relaxed text-fg-secondary">
              Research integrity, automated. Built for universities across
              Azerbaijan and the EaP region.
            </p>
          </div>

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-fg-tertiary">
              Product
            </h4>
            <ul className="mt-4 space-y-2.5">
              {productLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-fg-secondary transition-colors hover:text-fg-primary"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-fg-tertiary">
              Company
            </h4>
            <ul className="mt-4 space-y-2.5">
              {companyLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-fg-secondary transition-colors hover:text-fg-primary"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-fg-tertiary">
              Legal
            </h4>
            <ul className="mt-4 space-y-2.5">
              {legalLinks.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-fg-secondary transition-colors hover:text-fg-primary"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-12 flex flex-wrap items-center justify-between gap-3 border-t border-border-subtle pt-6">
          <p className="text-xs text-fg-tertiary">
            © 2026 ArtiProof. All rights reserved.
          </p>
          <p className="text-xs text-fg-tertiary">
            Research integrity, made transparent.
          </p>
        </div>
      </div>
    </footer>
  );
}
