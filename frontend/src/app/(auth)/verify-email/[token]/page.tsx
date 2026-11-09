"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { CheckCircle2, Loader2, MailCheck, XCircle } from "lucide-react";

type Status = "pending" | "success" | "error";

export default function VerifyEmailPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = use(params);
  const [status, setStatus] = useState<Status>("pending");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch("/api/auth/email/verify", {
          method: "POST",
          skipAuthRedirect: true,
          body: JSON.stringify({ token }),
        });
        if (cancelled) return;
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          setError(
            (data as { detail?: string }).detail ||
              "Invalid or expired verification link."
          );
          setStatus("error");
          return;
        }
        setStatus("success");
      } catch {
        if (cancelled) return;
        setError("Network error — please try again");
        setStatus("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <Card className="border-zinc-200 bg-white backdrop-blur-xl dark:border-zinc-800 dark:bg-zinc-900/50">
      <CardHeader className="text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-brand">
          {status === "pending" ? (
            <Loader2 className="h-6 w-6 animate-spin text-white" />
          ) : status === "success" ? (
            <CheckCircle2 className="h-6 w-6 text-white" />
          ) : (
            <XCircle className="h-6 w-6 text-white" />
          )}
        </div>
        <CardTitle className="text-2xl text-zinc-900 dark:text-white">
          {status === "pending"
            ? "Verifying…"
            : status === "success"
              ? "Email verified"
              : "Verification failed"}
        </CardTitle>
        <CardDescription className="text-zinc-600 dark:text-zinc-400">
          {status === "pending"
            ? "Confirming your link with the server."
            : status === "success"
              ? "Your email is now verified. You can return to your dashboard."
              : "We couldn't verify this link."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {status === "success" && (
          <div className="flex items-start gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-800 dark:border-emerald-700/40 dark:bg-emerald-900/20 dark:text-emerald-300">
            <MailCheck className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
            <span>Thanks — that&apos;s done.</span>
          </div>
        )}
        {status === "error" && (
          <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-400">
            {error}
          </div>
        )}
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-between">
          <Link
            href="/dashboard"
            className="text-sm text-brand hover:text-brand-hover dark:text-brand-fg"
          >
            Go to dashboard
          </Link>
          <Link
            href="/settings"
            className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
          >
            Open settings
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
