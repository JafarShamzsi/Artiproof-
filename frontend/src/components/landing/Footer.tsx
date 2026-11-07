"use client";

import { Shield, Twitter, Github, Linkedin } from "lucide-react";

const productLinks = [
  { label: "Scanner", href: "#" },
  { label: "Education Hub", href: "#" },
  { label: "Threat Feed", href: "#" },
  { label: "API", href: "#" },
  { label: "Pricing", href: "#" },
];

const companyLinks = [
  { label: "About", href: "#" },
  { label: "Blog", href: "#" },
  { label: "Careers", href: "#" },
  { label: "Press Kit", href: "#" },
  { label: "Contact", href: "#" },
];

const legalLinks = [
  { label: "Privacy Policy", href: "#" },
  { label: "Terms of Service", href: "#" },
  { label: "Cookie Policy", href: "#" },
  { label: "Security", href: "#" },
];

const socialLinks = [
  { icon: Twitter, label: "Twitter", href: "#" },
  { icon: Github, label: "GitHub", href: "#" },
  { icon: Linkedin, label: "LinkedIn", href: "#" },
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
              <span className="font-bold text-white">CivicGuards</span>
            </div>
            <p className="mt-2 text-sm text-zinc-500">
              Defending truth with intelligence
            </p>
            <div className="mt-4 flex items-center gap-3">
              {socialLinks.map((social) => (
                <a
                  key={social.label}
                  href={social.href}
                  aria-label={social.label}
                  className="text-zinc-500 transition-colors hover:text-white"
                >
                  <social.icon size={18} />
                </a>
              ))}
            </div>
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
            &copy; 2026 CivicGuards. All rights reserved.
          </p>
          <p className="text-sm text-zinc-500">Built to defend truth.</p>
        </div>
      </div>
    </footer>
  );
}
