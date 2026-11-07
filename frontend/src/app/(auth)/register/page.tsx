"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
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

const ROLES = [
  { value: "researcher", label: "Researcher" },
  { value: "faculty", label: "Faculty" },
  { value: "admin", label: "Institution Admin" },
];

export default function RegisterPage() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [institution, setInstitution] = useState("");
  const [role, setRole] = useState("researcher");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

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
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Registration failed");
        setLoading(false);
        return;
      }

      await signIn("credentials", {
        email,
        password,
        callbackUrl: "/dashboard",
      });
    } catch {
      setError("Something went wrong");
      setLoading(false);
    }
  };

  return (
    <Card className="border-zinc-800 bg-zinc-900/50 backdrop-blur-xl">
      <CardHeader className="text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-emerald-500">
          <Shield className="h-6 w-6 text-white" />
        </div>
        <CardTitle className="text-2xl text-white">Create an account</CardTitle>
        <CardDescription className="text-zinc-400">
          Join ArtiProof and protect research integrity
        </CardDescription>
      </CardHeader>

      <form onSubmit={handleSubmit}>
        <CardContent className="space-y-4">
          {error && (
            <div className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">
              {error}
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="fullName" className="text-zinc-300">
              Full Name <span className="text-red-400">*</span>
            </Label>
            <Input
              id="fullName"
              type="text"
              placeholder="Dr. Jane Smith"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              className="border-zinc-700 bg-zinc-800/50 text-white placeholder:text-zinc-500"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email" className="text-zinc-300">
              Email <span className="text-red-400">*</span>
            </Label>
            <Input
              id="email"
              type="email"
              placeholder="you@university.edu"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="border-zinc-700 bg-zinc-800/50 text-white placeholder:text-zinc-500"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password" className="text-zinc-300">
              Password <span className="text-red-400">*</span>
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
              className="border-zinc-700 bg-zinc-800/50 text-white placeholder:text-zinc-500"
            />
            <p id="password-hint" className="text-xs text-zinc-500">
              Minimum 8 characters. Use a passphrase or password manager.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="institution" className="text-zinc-300">Institution / University</Label>
            <Input
              id="institution"
              type="text"
              placeholder="e.g. ADA University"
              value={institution}
              onChange={(e) => setInstitution(e.target.value)}
              className="border-zinc-700 bg-zinc-800/50 text-white placeholder:text-zinc-500"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="role" className="text-zinc-300">Role</Label>
            <select
              id="role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full rounded-md border border-zinc-700 bg-zinc-800/50 px-3 py-2 text-sm text-white focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
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
            className="w-full bg-emerald-500 text-white hover:bg-emerald-600"
          >
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Create Account
          </Button>
          <div className="flex w-full items-center gap-3">
            <div className="h-px flex-1 bg-zinc-800" />
            <span className="text-xs uppercase tracking-wider text-zinc-500">or</span>
            <div className="h-px flex-1 bg-zinc-800" />
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={googleLoading}
            onClick={() => {
              setGoogleLoading(true);
              void signIn("google", { callbackUrl: "/dashboard" });
            }}
            className="w-full border-zinc-700 bg-zinc-900 text-white hover:bg-zinc-800 hover:text-white"
          >
            {googleLoading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Chrome className="mr-2 h-4 w-4" />
            )}
            Sign up with Google
          </Button>
          <p className="text-sm text-zinc-400">
            Already have an account?{" "}
            <Link href="/login" className="text-emerald-400 hover:text-emerald-300">
              Sign in
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}
