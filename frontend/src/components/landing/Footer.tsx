import { Shield } from "lucide-react";

// Anchor hrefs are prefixed with `/` so they resolve to the home page even when
// the footer renders on /privacy or /terms — bare `#pricing` would just look
// for that anchor on the current route.
const productLinks = [
  { label: "Source Verification", href: "/#features" },
  { label: "AI Detection", href: "/#features" },
  { label: "Citation Analysis", href: "/#features" },
  { label: "Pricing", href: "/#pricing" },
];

const companyLinks = [
  { label: "About", href: "/#how-it-works" },
  { label: "Contact", href: "mailto:info@example.invalid" },
];

const legalLinks = [
  { label: "Privacy Policy", href: "/privacy" },
  { label: "Terms of Service", href: "/terms" },
];

export function Footer() {
  return (
    <footer className="border-t border-zinc-800 bg-zinc-950">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          {/* Column 1: Brand */}
          <div>
            <div className="flex items-center gap-2">
              <Shield size={20} className="text-emerald-400" />
              <span className="font-bold text-white">ArtiProof</span>
            </div>
            <p className="mt-2 text-sm text-zinc-500">
              Research Integrity Platform
            </p>
            <p className="mt-4 text-xs text-zinc-600">
              Built for Azerbaijan & the EaP region
            </p>
          </div>

          {/* Column 2: Product */}
          <div>
            <h4 className="mb-4 text-sm font-semibold uppercase tracking-wider text-white">
              Product
            </h4>
            {productLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="mb-2 block text-sm text-zinc-500 transition-colors hover:text-zinc-300"
              >
                {link.label}
              </a>
            ))}
          </div>

          {/* Column 3: Company */}
          <div>
            <h4 className="mb-4 text-sm font-semibold uppercase tracking-wider text-white">
              Company
            </h4>
            {companyLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="mb-2 block text-sm text-zinc-500 transition-colors hover:text-zinc-300"
              >
                {link.label}
              </a>
            ))}
          </div>

          {/* Column 4: Legal */}
          <div>
            <h4 className="mb-4 text-sm font-semibold uppercase tracking-wider text-white">
              Legal
            </h4>
            {legalLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="mb-2 block text-sm text-zinc-500 transition-colors hover:text-zinc-300"
              >
                {link.label}
              </a>
            ))}
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="mt-12 flex flex-wrap items-center justify-between gap-4 border-t border-zinc-800 pt-8">
          <p className="text-sm text-zinc-600">
            &copy; 2026 ArtiProof. All rights reserved.
          </p>
          <p className="text-sm text-zinc-500">Research integrity, made transparent.</p>
        </div>
      </div>
    </footer>
  );
}
