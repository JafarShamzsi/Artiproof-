"use client";

import { Suspense, useEffect, useState } from "react";
import { signIn, useSession } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { backendUrl } from "@/lib/api";
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
import { Chrome, Shield, Loader2 } from "lucide-react";
import { InvitationConsent } from "@/components/invitation-consent";

// Admin role is intentionally not exposed on the public sign-up form — it's
// privileged and assigned out-of-band by an existing admin. The backend also
// enforces this server-side (see backend/app/routers/auth.py:register).
const ROLES = [
  { value: "researcher", label: "Researcher" },
  { value: "faculty", label: "Faculty" },
];

// Plans the pricing page can route here as ?plan=. Anything else is
// ignored — the backend tolerates unknown plans by skipping the
// audit-row write, but the frontend also tightens the surface.
const KNOWN_PLANS = new Set(["free", "pro", "team"]);

// Persistence for the plan intent. Stored as a first-party cookie (7d
// TTL) so a user who reads the pricing page, clicks "Start Pro",
// closes the tab, then comes back via /register tomorrow still
// arrives carrying the intent.
const PLAN_COOKIE = "artiproof_plan_intent";
const PLAN_COOKIE_MAX_AGE_S = 60 * 60 * 24 * 7;

function readPlanCookie(): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${PLAN_COOKIE}=`;
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) {
      const val = trimmed.slice(prefix.length);
      return KNOWN_PLANS.has(val) ? val : null;
    }
  }
  return null;
}

function writePlanCookie(plan: string): void {
  if (typeof document === "undefined") return;
  // Lax so the cookie comes through on a normal pricing-page click;
  // path=/ so it's visible to the register route regardless of nesting.
  document.cookie = `${PLAN_COOKIE}=${plan}; Max-Age=${PLAN_COOKIE_MAX_AGE_S}; Path=/; SameSite=Lax`;
}

function clearPlanCookie(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${PLAN_COOKIE}=; Max-Age=0; Path=/; SameSite=Lax`;
}

export default function RegisterPage() {
  // useSearchParams (inside RegisterPageInner) requires a Suspense
  // boundary in Next 16's App Router — otherwise the static-build pass
  // throws. The fallback matches the form's loaded-but-empty look so
  // the page doesn't flash.
  return (
    <Suspense
      fallback={
        <Card className="border-zinc-200 bg-white backdrop-blur-xl dark:border-zinc-800 dark:bg-zinc-900/50">
          <CardHeader className="text-center">
            <CardTitle>Loading…</CardTitle>
          </CardHeader>
        </Card>
      }
    >
      <RegisterPageInner />
    </Suspense>
  );
}

function RegisterPageInner() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [institution, setInstitution] = useState("");
  const [role, setRole] = useState("researcher");
  const [intentPlan, setIntentPlan] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const searchParams = useSearchParams();
  const inviteToken = searchParams?.get("invite");
  const { status: sessionStatus } = useSession();
  const callbackUrl = inviteToken ? `/register?invite=${encodeURIComponent(inviteToken)}` : "/dashboard";

  // On mount: prefer ?plan=, fall back to a previously-stored cookie,
  // and write the cookie when we land via query so the intent
  // survives a tab-close mid-signup. document.cookie is browser-only —
  // the post-mount setState is the standard "read once on client" path
  // that the lint rule is conservatively flagging.
  useEffect(() => {
    const fromQuery = searchParams?.get("plan");
    if (fromQuery && KNOWN_PLANS.has(fromQuery)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIntentPlan(fromQuery);
      writePlanCookie(fromQuery);
      return;
    }
    const fromCookie = readPlanCookie();
    if (fromCookie) {
      setIntentPlan(fromCookie);
    }
  }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password || password.length < 8 || !fullName) {
      setError("Please fill all required fields (password must be 8+ characters)");
      return;
    }
    setLoading(true);
    setError("");

    try {
      const res = await fetch(backendUrl("/api/auth/register"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: fullName,
          email,
          password,
          institution: institution || undefined,
          role,
          // Plan intent ships with the signup so the backend can log a
          // tier_change_audits row with reason="signup_intent" — the
          // funnel marker. Tier itself stays free until the (future)
          // payment processor confirms.
          intent_plan: intentPlan || undefined,
          invite_token: inviteToken || undefined,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Registration failed");
        setLoading(false);
        return;
      }

      // Intent has been recorded server-side; clear the cookie so
      // it doesn't follow the user into the dashboard.
      clearPlanCookie();

      await signIn("credentials", {
        email,
        password,
        callbackUrl,
      });
    } catch {
      setError("Something went wrong");
      setLoading(false);
    }
  };

  // NextAuth update() temporarily reports loading. Keep the same consent
  // instance through that refresh; it still gates actions on authentication.
  // Actual auth loss returns to signup and discards the prior consent state.
  if (inviteToken && sessionStatus !== "unauthenticated") {
    return <InvitationConsent key={inviteToken} token={inviteToken} />;
  }

  return (
    <Card className="border-zinc-200 bg-white backdrop-blur-xl dark:border-zinc-800 dark:bg-zinc-900/50">
      <CardHeader className="text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-brand">
          <Shield className="h-6 w-6 text-white" />
        </div>
        <CardTitle className="text-2xl text-zinc-900 dark:text-white">Create an account</CardTitle>
        <CardDescription className="text-zinc-600 dark:text-zinc-400">
          Join ArtiProof and protect research integrity
        </CardDescription>
      </CardHeader>

      <form onSubmit={handleSubmit}>
        <CardContent className="space-y-4">
          {inviteToken && <InvitationConsent key={inviteToken} token={inviteToken} />}
          {error && (
            <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-400">
              {error}
            </div>
          )}
          {intentPlan && intentPlan !== "free" && (
            <div
              role="status"
              className="rounded-lg border border-brand/30 bg-brand/5 p-3 text-sm text-zinc-700 dark:text-zinc-300"
            >
              You&apos;re signing up to start on the{" "}
              <span className="font-semibold capitalize">{intentPlan}</span>{" "}
              plan. You&apos;ll stay on the free tier until billing is set
              up — no surprise charges.
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="fullName" className="text-zinc-700 dark:text-zinc-300">
              Full Name <span className="text-red-600 dark:text-red-400">*</span>
            </Label>
            <Input
              id="fullName"
              type="text"
              placeholder="Dr. Jane Smith"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              className="border-zinc-300 bg-white text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white dark:placeholder:text-zinc-500"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email" className="text-zinc-700 dark:text-zinc-300">
              Email <span className="text-red-600 dark:text-red-400">*</span>
            </Label>
            <Input
              id="email"
              type="email"
              placeholder="you@university.edu"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="border-zinc-300 bg-white text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white dark:placeholder:text-zinc-500"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password" className="text-zinc-700 dark:text-zinc-300">
              Password <span className="text-red-600 dark:text-red-400">*</span>
            </Label>
            <Input
              id="password"
              type="password"
              placeholder="At least 8 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              aria-describedby="password-hint"
              className="border-zinc-300 bg-white text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white dark:placeholder:text-zinc-500"
            />
            <p id="password-hint" className="text-xs text-zinc-500">
              Minimum 8 characters. Use a passphrase or password manager.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="institution" className="text-zinc-700 dark:text-zinc-300">Institution / University</Label>
            <Input
              id="institution"
              type="text"
              placeholder="e.g. ADA University"
              value={institution}
              onChange={(e) => setInstitution(e.target.value)}
              className="border-zinc-300 bg-white text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white dark:placeholder:text-zinc-500"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="role" className="text-zinc-700 dark:text-zinc-300">Role</Label>
            <select
              id="role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-brand/50 focus:outline-none focus:ring-1 focus:ring-brand/50 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
            >
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>
        </CardContent>
        <CardFooter className="flex flex-col gap-4">
          <Button
            type="submit"
            disabled={loading}
            className="w-full bg-brand text-white hover:bg-brand-hover"
          >
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Create Account
          </Button>
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
              void signIn("google", { callbackUrl });
            }}
            className="w-full border-zinc-300 bg-white text-zinc-900 hover:bg-zinc-100 hover:text-zinc-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-white dark:hover:bg-zinc-800 dark:hover:text-white"
          >
            {googleLoading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Chrome className="mr-2 h-4 w-4" />
            )}
            Sign up with Google
          </Button>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Already have an account?{" "}
            <Link href="/login" className="text-brand hover:text-brand-hover dark:text-brand-fg">
              Sign in
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}
