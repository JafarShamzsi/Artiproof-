"use client";

import { FormEvent, useState } from "react";
import { LampEffect } from "./shared/LampEffect";

export function CTASection() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setSuccess(false);

    try {
      const res = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      const data = await res.json();

      if (res.status === 409) {
        setError("You're already on the list!");
      } else if (!res.ok) {
        setError(data.message || "Something went wrong. Please try again.");
      } else {
        setSuccess(true);
        setEmail("");
      }
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <LampEffect>
      <div className="mx-auto max-w-2xl px-6 text-center">
        <h2 className="text-4xl font-bold text-white">
          Join the Fight Against Misinformation
        </h2>
        <p className="mt-4 text-zinc-400">
          Get early access to the most advanced misinformation intelligence
          platform.
        </p>

        <form
          onSubmit={handleSubmit}
          className="mx-auto mt-8 flex max-w-md gap-2"
        >
          <input
            type="email"
            required
            placeholder="Enter your email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-3 text-white placeholder:text-zinc-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
          />
          <button
            type="submit"
            disabled={loading}
            className="whitespace-nowrap rounded-lg bg-emerald-500 px-6 py-3 font-medium text-white transition-all hover:bg-emerald-600 disabled:opacity-60"
          >
            {loading ? "Joining..." : "Join Waitlist"}
          </button>
        </form>

        {success && (
          <p className="mt-4 text-sm text-emerald-400">
            You&apos;re in! We&apos;ll notify you when we launch.
          </p>
        )}

        {error && (
          <p className="mt-4 text-sm text-red-400">{error}</p>
        )}

        <p className="mt-6 text-sm text-zinc-500">
          Join 2,400+ truth-seekers already on the list
        </p>
      </div>
    </LampEffect>
  );
}
