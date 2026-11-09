import Link from "next/link";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

export const metadata = {
  title: "Security & Vulnerability Disclosure — ArtiProof",
  description:
    "How to responsibly disclose a security issue in ArtiProof, what we treat as in-scope, and what reporters can expect from us.",
};

/**
 * Security disclosure landing — referenced by /.well-known/security.txt
 * (RFC 9116) as the canonical Policy URL. Keep the contact email and SLA
 * here in sync with security.txt; security researchers will check both.
 */
export default function SecurityPage() {
  return (
    <>
      <Navbar />
      <main
        id="main-content"
        tabIndex={-1}
        className="relative z-10 min-h-[100dvh] bg-zinc-950 pb-24 pt-32"
      >
        <article className="mx-auto max-w-3xl px-6 text-zinc-300">
          <Link
            href="/"
            className="text-sm text-emerald-400 hover:text-emerald-300"
          >
            &larr; Back to home
          </Link>

          <h1 className="mt-6 text-4xl font-bold text-white">
            Security & Vulnerability Disclosure
          </h1>
          <p className="mt-2 text-sm text-zinc-500">Last updated: May 2026</p>

          <div className="prose prose-invert mt-10 max-w-none space-y-8">
            <section>
              <h2 className="text-2xl font-semibold text-white">
                Reporting a vulnerability
              </h2>
              <p className="mt-3 text-zinc-400">
                If you believe you have found a security issue in ArtiProof
                — anything that could affect the confidentiality, integrity,
                or availability of researcher data — please email{" "}
                <a
                  href="mailto:security@artiproof.com"
                  className="text-emerald-400 hover:text-emerald-300"
                >
                  security@artiproof.com
                </a>{" "}
                with a clear reproduction, the affected URL or endpoint, and
                your name (or a handle) for credit.
              </p>
              <p className="mt-3 text-zinc-400">
                A machine-readable copy of this contact is also published at{" "}
                <Link
                  href="/.well-known/security.txt"
                  className="text-emerald-400 hover:text-emerald-300"
                >
                  /.well-known/security.txt
                </Link>{" "}
                per RFC 9116.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold text-white">
                What you can expect
              </h2>
              <ul className="mt-3 list-inside list-disc space-y-2 text-zinc-400">
                <li>
                  Acknowledgement within{" "}
                  <strong className="text-zinc-200">2 business days</strong>{" "}
                  of receipt.
                </li>
                <li>
                  An initial triage and severity assessment within{" "}
                  <strong className="text-zinc-200">5 business days</strong>.
                </li>
                <li>
                  Coordinated disclosure once a fix is in production. We will
                  credit you in the changelog unless you ask us not to.
                </li>
                <li>
                  No legal action against good-faith research that follows
                  this policy. Test on your own accounts only — do not
                  access other users&apos; data.
                </li>
              </ul>
            </section>

            <section>
              <h2 className="text-2xl font-semibold text-white">
                Scope &amp; out-of-scope
              </h2>
              <p className="mt-3 text-zinc-400">
                In scope: the production web application at artiproof.com, the
                public API under{" "}
                <code className="rounded bg-zinc-800 px-1.5 py-0.5 text-sm">
                  /api/*
                </code>
                , and any subdomains we own. Out of scope:
              </p>
              <ul className="mt-3 list-inside list-disc space-y-2 text-zinc-400">
                <li>
                  Volumetric DoS / spam. Test our rate limits responsibly.
                </li>
                <li>
                  Reports that consist only of an automated scanner&apos;s
                  output with no demonstrated impact.
                </li>
                <li>
                  Social engineering of ArtiProof staff, customers, or
                  partners.
                </li>
                <li>
                  Third-party services we use (Resend, Gemini, CrossRef,
                  OpenAlex). Report those to their respective vendors.
                </li>
              </ul>
            </section>

            <section>
              <h2 className="text-2xl font-semibold text-white">Encryption</h2>
              <p className="mt-3 text-zinc-400">
                Sensitive details can be encrypted with our PGP key, available
                on request from{" "}
                <a
                  href="mailto:security@artiproof.com"
                  className="text-emerald-400 hover:text-emerald-300"
                >
                  security@artiproof.com
                </a>
                .
              </p>
            </section>
          </div>
        </article>
      </main>
      <Footer />
    </>
  );
}
