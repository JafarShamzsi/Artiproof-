"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Link from "next/link";
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
import { Chrome, Shield, Loader2, KeyRound } from "lucide-react";

type Stage = "credentials" | "totp" | "backup";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [stage, setStage] = useState<Stage>("credentials");
  const [challengeToken, setChallengeToken] = useState("");
  const [twoFactorCode, setTwoFactorCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  async function submitCredentials() {
    setLoading(true);
    setError("");

    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });

    if (result?.error) {
      // The credentials provider encodes a 2FA challenge as a JSON payload in
      // the thrown Error message; everything else is a plain string.
      try {
        const parsed = JSON.parse(result.error) as {
          twoFactorChallenge?: boolean;
          challengeToken?: string;
        };
        if (parsed.twoFactorChallenge && parsed.challengeToken) {
          setChallengeToken(parsed.challengeToken);
          setStage("totp");
          setLoading(false);
          return;
        }
      } catch {
        // Not JSON — treat as a normal error message below.
      }
      setError(result.error || "Invalid email or password");
      setLoading(false);
      return;
    }

    router.push("/dashboard");
  }

  async function submitTwoFactor() {
    setLoading(true);
    setError("");

    const result = await signIn("credentials", {
      email,
      password,
      challengeToken,
      twoFactorCode: twoFactorCode.trim(),
      redirect: false,
    });

    if (result?.error) {
      setError(result.error || "Invalid code");
      setLoading(false);
      return;
    }

    router.push("/dashboard");
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (stage === "credentials") {
      await submitCredentials();
    } else {
      await submitTwoFactor();
    }
  };

  const onTwoFactor = stage !== "credentials";

  return (
    <Card className="border-zinc-200 bg-white backdrop-blur-xl dark:border-zinc-800 dark:bg-zinc-900/50">
      <CardHeader className="text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-brand">
          {onTwoFactor ? (
            <KeyRound className="h-6 w-6 text-white" />
          ) : (
            <Shield className="h-6 w-6 text-white" />
          )}
        </div>
        <CardTitle className="text-2xl text-zinc-900 dark:text-white">
          {onTwoFactor ? "Two-factor authentication" : "Welcome back"}
        </CardTitle>
        <CardDescription className="text-zinc-600 dark:text-zinc-400">
          {stage === "totp"
            ? "Enter the code from your authenticator app"
            : stage === "backup"
              ? "Enter one of your backup codes"
              : "Sign in to your ArtiProof account"}
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit}>
        <CardContent className="space-y-4">
          {error && (
            <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-400">
              {error}
            </div>
          )}

          {stage === "credentials" && (
            <>
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
                  className="border-zinc-300 bg-white text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white dark:placeholder:text-zinc-500"
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password" className="text-zinc-700 dark:text-zinc-300">
                    Password
                  </Label>
                  <Link
                    href="/forgot-password"
                    className="text-xs text-brand hover:text-brand-hover dark:text-brand-fg"
                  >
                    Forgot password?
                  </Link>
                </div>
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="border-zinc-300 bg-white text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white dark:placeholder:text-zinc-500"
                />
              </div>
            </>
          )}

          {onTwoFactor && (
            <div className="space-y-2">
              <Label htmlFor="totp-code" className="text-zinc-700 dark:text-zinc-300">
                {stage === "totp" ? "6-digit code" : "Backup code"}
              </Label>
              <Input
                id="totp-code"
                type="text"
                inputMode={stage === "totp" ? "numeric" : "text"}
                autoComplete="one-time-code"
                pattern={stage === "totp" ? "[0-9]{6}" : undefined}
                maxLength={stage === "totp" ? 6 : 12}
                placeholder={stage === "totp" ? "123456" : "ABCDEF12"}
                value={twoFactorCode}
                onChange={(e) => setTwoFactorCode(e.target.value)}
                required
                autoFocus
                className="border-zinc-300 bg-white font-mono text-lg tracking-widest text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white dark:placeholder:text-zinc-500"
              />
              <button
                type="button"
                onClick={() => {
                  setTwoFactorCode("");
                  setError("");
                  setStage(stage === "totp" ? "backup" : "totp");
                }}
                className="text-xs text-brand hover:text-brand-hover dark:text-brand-fg"
              >
                {stage === "totp"
                  ? "Use a backup code instead"
                  : "Use authenticator code instead"}
              </button>
            </div>
          )}
        </CardContent>
        <CardFooter className="flex flex-col gap-4">
          <Button
            type="submit"
            disabled={loading}
            className="w-full bg-brand text-white hover:bg-brand-hover"
          >
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            {onTwoFactor ? "Verify code" : "Sign In"}
          </Button>

          {onTwoFactor ? (
            <button
              type="button"
              onClick={() => {
                setStage("credentials");
                setTwoFactorCode("");
                setChallengeToken("");
                setError("");
              }}
              className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
            >
              Back to sign in
            </button>
          ) : (
            <>
              <div className="flex w-full items-center gap-3">
                <div className="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" />
                <span className="text-xs uppercase tracking-wider text-zinc-500">or</span>
                <div className="h-px flex-1 bg-zinc-200 dark:bg-zinc-800" />
              </div>
              <Button
                type="button"
                variant="outline"
                disabled={googleLoading}
                onClick={() => {
                  setGoogleLoading(true);
                  void signIn("google", { callbackUrl: "/dashboard" });
                }}
                className="w-full border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-100 hover:text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white dark:hover:bg-zinc-800 dark:hover:text-white"
              >
                {googleLoading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Chrome className="mr-2 h-4 w-4" />
                )}
                Continue with Google
              </Button>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">
                Don&apos;t have an account?{" "}
                <Link
                  href="/register"
                  className="text-brand hover:text-brand-hover dark:text-brand-fg"
                >
                  Sign up
                </Link>
              </p>
            </>
          )}
        </CardFooter>
      </form>
    </Card>
  );
}
