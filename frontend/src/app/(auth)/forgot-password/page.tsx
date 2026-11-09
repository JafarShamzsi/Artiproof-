"use client";

import { useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { KeyRound, Loader2 } from "lucide-react";

interface ForgotResponse {
  detail: string;
  dev_reset_url?: string;
}

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ForgotResponse | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await apiFetch("/api/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError((data as { detail?: string }).detail || "Something went wrong");
        return;
      }
      setResult((await res.json()) as ForgotResponse);
    } catch {
      setError("Network error — please try again");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="border-zinc-200 bg-white backdrop-blur-xl dark:border-zinc-800 dark:bg-zinc-900/50">
      <CardHeader className="text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-brand">
          <KeyRound className="h-6 w-6 text-white" />
        </div>
        <CardTitle className="text-2xl text-zinc-900 dark:text-white">
          Reset your password
        </CardTitle>
        <CardDescription className="text-zinc-600 dark:text-zinc-400">
          Enter your email and we&apos;ll send you a link to set a new one.
        </CardDescription>
      </CardHeader>

      {result ? (
        <CardContent className="space-y-4">
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-800 dark:border-emerald-700/40 dark:bg-emerald-900/20 dark:text-emerald-300">
            If that account exists, a reset link has been sent.
          </div>
          {result.dev_reset_url && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-800 dark:border-amber-600/40 dark:bg-amber-900/20 dark:text-amber-300">
              <p className="mb-2 font-medium">Dev: open this link to reset</p>
              <a
                href={result.dev_reset_url}
                className="block break-all rounded border border-amber-500/30 bg-white/40 px-2 py-1 font-mono text-xs underline-offset-2 hover:underline dark:bg-black/40"
              >
                {result.dev_reset_url}
              </a>
            </div>
          )}
          <Link
            href="/login"
            className="block text-center text-sm text-brand hover:text-brand-hover dark:text-brand-fg"
          >
            Back to sign in
          </Link>
        </CardContent>
      ) : (
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-400">
                {error}
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="email" className="text-zinc-700 dark:text-zinc-300">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="border-zinc-300 bg-white text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white dark:placeholder:text-zinc-500"
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-4">
            <Button
              type="submit"
              disabled={loading || !email}
              className="w-full bg-brand text-white hover:bg-brand-hover"
            >
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Send reset link
            </Button>
            <Link
              href="/login"
              className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
            >
              Back to sign in
            </Link>
          </CardFooter>
        </form>
      )}
    </Card>
  );
}
