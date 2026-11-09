import Link from "next/link";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

export const metadata = {
  title: "Terms of Service — ArtiProof",
  description:
    "The terms governing your use of ArtiProof, the research integrity platform.",
};

export default function TermsPage() {
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

          <h1 className="mt-6 text-4xl font-bold text-white">
            Terms of Service
          </h1>
          <p className="mt-2 text-sm text-zinc-500">
            Last updated: January 2026
          </p>

          <div className="prose prose-invert mt-10 max-w-none space-y-8">
            <section>
              <h2 className="text-2xl font-semibold text-white">
                Acceptance of terms
              </h2>
              <p className="mt-3 text-zinc-400">
                By creating an account or using ArtiProof you agree to these
                terms. If you don&rsquo;t agree, don&rsquo;t use the service.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold text-white">
                What ArtiProof is — and isn&rsquo;t
              </h2>
              <p className="mt-3 text-zinc-400">
                ArtiProof analyses content you submit and produces a report
                covering source credibility, AI-likelihood, citation health,
                and (where applicable) researcher integrity. The report is a
                signal, not a verdict. It is intended to support human review,
                not replace it. We do not guarantee that any specific
                conclusion is correct.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold text-white">
                Acceptable use
              </h2>
              <ul className="mt-3 list-disc space-y-2 pl-6 text-zinc-400">
                <li>
                  Don&rsquo;t submit content you&rsquo;re not allowed to
                  process — for example, copyrighted material you don&rsquo;t
                  have rights to, or sensitive personal data.
                </li>
                <li>
                  Don&rsquo;t use ArtiProof to harass individual researchers or
                  to publish unverified accusations of misconduct.
                </li>
                <li>
                  Don&rsquo;t attempt to bypass rate limits, share credentials,
                  or scrape the platform.
                </li>
                <li>
                  Don&rsquo;t reverse-engineer the service or use it to train
                  competing models.
                </li>
              </ul>
            </section>

            <section>
              <h2 className="text-2xl font-semibold text-white">
                Plans &amp; billing
              </h2>
              <p className="mt-3 text-zinc-400">
                The Free plan includes 10 source checks per month. Pro is
                $20/month (or $13/month billed yearly) and includes 200 checks
                plus the full feature set. Institution pricing is per-deal —
                contact us. Paid plans renew automatically until cancelled; you
                can cancel any time and keep access through the end of your
                current billing period.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold text-white">
                Your content
              </h2>
              <p className="mt-3 text-zinc-400">
                You retain ownership of everything you submit. You grant us a
                limited licence to process it solely to produce your report and
                run the service. We don&rsquo;t use submissions to train
                models. See the{" "}
                <Link
                  href="/privacy"
                  className="text-emerald-400 hover:text-emerald-300"
                >
                  Privacy Policy
                </Link>{" "}
                for details.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold text-white">
                Termination
              </h2>
              <p className="mt-3 text-zinc-400">
                You can delete your account at any time. We may suspend or
                terminate accounts that violate these terms or applicable law.
              </p>
            </section>

            <section>
              <h2 className="text-2xl font-semibold text-white">Contact</h2>
              <p className="mt-3 text-zinc-400">
                Questions? Email{" "}
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
