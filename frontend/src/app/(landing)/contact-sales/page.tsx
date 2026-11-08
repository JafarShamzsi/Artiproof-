"use client";

import { useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { backendUrl } from "@/lib/api";

/**
 * Institution-tier lead capture. Posts to /api/sales/inquiry which
 * stores the lead in sales_leads and (best-effort) emails support.
 *
 * Validation is intentionally light: email + name are the only
 * required fields. Pre-procurement researchers won't fill out long
 * forms; a one-line message + a real email address is enough to
 * start the conversation.
 */

const TEAM_SIZES = [
  { value: "", label: "Select a team size" },
  { value: "1-5", label: "1-5 people" },
  { value: "6-25", label: "6-25 people" },
  { value: "26-100", label: "26-100 people" },
  { value: "100+", label: "100+ people" },
];

export default function ContactSalesPage() {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [institution, setInstitution] = useState("");
  const [teamSize, setTeamSize] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !name.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(backendUrl("/api/sales/inquiry"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          name: name.trim(),
          institution: institution.trim() || null,
          team_size: teamSize || null,
          message: message.trim() || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "We couldn't send your message. Try again?");
        return;
      }
      setSubmitted(true);
    } catch {
      setError("Network error — please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Navbar />
      <main
        id="main-content"
        tabIndex={-1}
        className="relative z-10 min-h-[100dvh] bg-zinc-950 pb-24 pt-32"
      >
        <article className="mx-auto max-w-2xl px-6 text-zinc-300">
          <Link
            href="/#pricing"
            className="text-sm text-emerald-400 hover:text-emerald-300"
          >
            &larr; Back to pricing
          </Link>

          <h1 className="mt-6 text-4xl font-bold text-white">
            Talk to sales
          </h1>
          <p className="mt-3 max-w-xl text-zinc-400">
            Institutional pricing, on-prem options, custom integrations,
            and pilot programs for research-integrity offices. Tell us a
            bit about your team and we&apos;ll get back within two
            business days.
          </p>

          {submitted ? (
            <div
              role="status"
              className="mt-10 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-6 text-sm text-emerald-100"
            >
              <p className="font-semibold">Thanks — we got it.</p>
              <p className="mt-2 text-emerald-200/80">
                We&apos;ll reply to <strong>{email}</strong> within two
                business days. If you don&apos;t hear from us, please
                check your spam folder and then email{" "}
                <a
                  href="mailto:info@example.invalid"
                  className="underline-offset-2 hover:underline"
                >
                  info@example.invalid
                </a>{" "}
                directly.
              </p>
            </div>
          ) : (
            <form
              onSubmit={handleSubmit}
              className="mt-10 space-y-5"
              aria-describedby={error ? "sales-error" : undefined}
            >
              {error && (
                <div
                  id="sales-error"
                  role="alert"
                  className="rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200"
                >
                  {error}
                </div>
              )}

              <div>
                <label
                  htmlFor="sales-name"
                  className="block text-sm font-medium text-zinc-200"
                >
                  Your name <span className="text-rose-400">*</span>
                </label>
                <input
                  id="sales-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  className="mt-1 block w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white placeholder:text-zinc-500 focus:border-emerald-500 focus:outline-none"
                  placeholder="Dr. Jane Smith"
                />
              </div>

              <div>
                <label
                  htmlFor="sales-email"
                  className="block text-sm font-medium text-zinc-200"
                >
                  Work email <span className="text-rose-400">*</span>
                </label>
                <input
                  id="sales-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="mt-1 block w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white placeholder:text-zinc-500 focus:border-emerald-500 focus:outline-none"
                  placeholder="jsmith@university.edu"
                />
              </div>

              <div>
                <label
                  htmlFor="sales-institution"
                  className="block text-sm font-medium text-zinc-200"
                >
                  Institution
                </label>
                <input
                  id="sales-institution"
                  type="text"
                  value={institution}
                  onChange={(e) => setInstitution(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white placeholder:text-zinc-500 focus:border-emerald-500 focus:outline-none"
                  placeholder="Baku State University"
                />
              </div>

              <div>
                <label
                  htmlFor="sales-team-size"
                  className="block text-sm font-medium text-zinc-200"
                >
                  Team size
                </label>
                <select
                  id="sales-team-size"
                  value={teamSize}
                  onChange={(e) => setTeamSize(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white focus:border-emerald-500 focus:outline-none"
                >
                  {TEAM_SIZES.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label
                  htmlFor="sales-message"
                  className="block text-sm font-medium text-zinc-200"
                >
                  What are you trying to solve?
                </label>
                <textarea
                  id="sales-message"
                  rows={4}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  maxLength={4000}
                  className="mt-1 block w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white placeholder:text-zinc-500 focus:border-emerald-500 focus:outline-none"
                  placeholder="A few sentences about your team and what you'd want from ArtiProof. Optional."
                />
              </div>

              <button
                type="submit"
                disabled={submitting || !email.trim() || !name.trim()}
                className="inline-flex items-center rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-zinc-950 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Sending…" : "Send inquiry"}
              </button>
            </form>
          )}
        </article>
      </main>
      <Footer />
    </>
  );
}
