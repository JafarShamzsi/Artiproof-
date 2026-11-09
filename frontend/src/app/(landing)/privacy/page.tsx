import Link from "next/link";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

export const metadata = {
  title: "Privacy Policy — ArtiProof",
  description:
    "How ArtiProof collects, uses, and safeguards your data when you use the research integrity platform.",
};

export default function PrivacyPage() {
  return (
    <>
      <Navbar />
      <main id="main-content" tabIndex={-1} className="relative z-10 min-h-[100dvh] bg-zinc-950 pt-32 pb-24">
        <article className="mx-auto max-w-3xl px-6 text-zinc-300">
          <Link
            href="/"
            className="text-sm text-emerald-400 hover:text-emerald-300"
          >
            &larr; Back to home
          </Link>

          <h1 className="mt-6 text-4xl font-bold text-white">Privacy Policy</h1>
          <p className="mt-2 text-sm text-zinc-500">
            Last updated: January 2026
          </p>

          <div className="prose prose-invert mt-10 max-w-none space-y-8">
            <section>
              <h2 className="text-2xl font-semibold text-white">Overview</h2>
              <p className="mt-3 text-zinc-400">
                ArtiProof is a research integrity platform. This page explains
                what we collect when you use the service, how we use it, and
                the controls you have over your data. We collect the minimum
                data needed to run analyses you request and to keep your
                account secure.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold text-white">
                What we collect
              </h2>
              <ul className="mt-3 list-disc space-y-2 pl-6 text-zinc-400">
                <li>
                  <strong className="text-zinc-300">Account data</strong> —
                  email, name, institution, and (for password sign-in) a hashed
                  password. We never store your password in plain text.
                </li>
                <li>
                  <strong className="text-zinc-300">Submitted content</strong>{" "}
                  — URLs, text, and PDFs you submit for verification. Stored
                  with your account so you can re-open past reports.
                </li>
                <li>
                  <strong className="text-zinc-300">Analysis output</strong> —
                  credibility scores, claim verdicts, AI-detection scores, and
                  citation graphs derived from your submissions.
                </li>
                <li>
                  <strong className="text-zinc-300">Operational logs</strong> —
                  request metadata (timestamps, status codes, IP for rate
                  limiting). Retained for 30 days unless required for security
                  investigation.
                </li>
              </ul>
            </section>

            <section>
              <h2 className="text-2xl font-semibold text-white">
                How we use it
              </h2>
              <p className="mt-3 text-zinc-400">
                Your submitted content and derived analysis are visible only to
                you, except when you generate a share link — those reports are
                accessible to anyone with the link until you revoke it. We do
                not sell user data and we do not use your submitted content to
                train models.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold text-white">
                Third-party processors
              </h2>
              <p className="mt-3 text-zinc-400">
                Source verification calls Google&rsquo;s Gemini API and Fact
                Check Tools. Citation analysis calls Semantic Scholar, OpenAlex,
                CrossRef, and (when configured) Scopus. Submitted content is
                sent to these providers only as needed to perform the analysis
                you requested.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold text-white">Your rights</h2>
              <p className="mt-3 text-zinc-400">
                You can export, correct, or delete your data at any time from
                Settings, or by emailing{" "}
                <a
                  href="mailto:info@artiproof.com"
                  className="text-emerald-400 hover:text-emerald-300"
                >
                  info@artiproof.com
                </a>
                . Account deletion removes your submissions, analyses, and
                shared report links.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold text-white">Contact</h2>
              <p className="mt-3 text-zinc-400">
                Questions about this policy? Reach us at{" "}
                <a
                  href="mailto:info@artiproof.com"
                  className="text-emerald-400 hover:text-emerald-300"
                >
                  info@artiproof.com
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
