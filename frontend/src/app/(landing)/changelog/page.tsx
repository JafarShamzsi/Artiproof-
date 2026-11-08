import Link from "next/link";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

export const metadata = {
  title: "Snapshot scope — ArtiProof showcase",
  description: "Scope of this source-review snapshot, not a production release log.",
};

export default function ChangelogPage() {
  return (
    <>
      <Navbar />
      <main id="main-content" tabIndex={-1} className="mx-auto min-h-[70vh] max-w-3xl px-6 pb-24 pt-32">
        <Link href="/" className="underline">Back to home</Link>
        <h1 className="mt-6 text-4xl font-bold">Source snapshot scope</h1>
        <p className="mt-6">This judges/review repository contains a sanitized implementation snapshot. It does not publish the production release log or internal operational history.</p>
        <p className="mt-4">This is not a claim about the project&apos;s original start date. Review the repository README for included features, adaptations, attribution and verification limits.</p>
      </main>
      <Footer />
    </>
  );
}
