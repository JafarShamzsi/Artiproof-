"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { User, Bell, Save, Loader2, Eye } from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";
import { apiFetch } from "@/lib/api";

type UserRole = "researcher" | "faculty" | "admin";

interface ProfileResponse {
  id: string;
  email: string;
  full_name: string;
  institution: string | null;
  role: string;
  created_at: string;
}

export default function SettingsPage() {
  const { data: session } = useSession();
  const { highContrast, toggleHighContrast } = useTheme();

  const [fullName, setFullName] = useState("");
  const [institution, setInstitution] = useState("");
  const [role, setRole] = useState<UserRole>("researcher");
  const [email, setEmail] = useState("");

  const [loadingProfile, setLoadingProfile] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch("/api/auth/me")
      .then((r) => (r.ok ? (r.json() as Promise<ProfileResponse>) : null))
      .then((profile) => {
        if (cancelled || !profile) return;
        setFullName(profile.full_name || "");
        setInstitution(profile.institution || "");
        setRole((profile.role as UserRole) || "researcher");
        setEmail(profile.email);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoadingProfile(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/api/auth/me", {
        method: "PUT",
        body: JSON.stringify({
          full_name: fullName,
          institution: institution || null,
          role,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Failed to save profile");
        return;
      }

      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setError("Network error — please try again");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-zinc-400">Manage your profile and preferences.</p>
      </div>

      <Card className="border-zinc-800 bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-white">
            <User className="h-5 w-5 text-zinc-400" /> Profile
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {loadingProfile ? (
            <div className="flex justify-center py-6">
              <Loader2 className="h-5 w-5 animate-spin text-zinc-500" />
            </div>
          ) : (
            <>
              {error && (
                <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400">
                  {error}
                </div>
              )}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label className="text-zinc-300">Full Name</Label>
                  <Input
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="border-zinc-700 bg-zinc-800/50 text-white"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-zinc-300">Email</Label>
                  <Input
                    value={email || session?.user?.email || ""}
                    disabled
                    className="border-zinc-700 bg-zinc-800/50 text-zinc-500"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-zinc-300">Institution / University</Label>
                <Input
                  value={institution}
                  onChange={(e) => setInstitution(e.target.value)}
                  placeholder="e.g. ADA University"
                  className="border-zinc-700 bg-zinc-800/50 text-white placeholder:text-zinc-500"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-zinc-300">Role</Label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value as UserRole)}
                  className="w-full rounded-md border border-zinc-700 bg-zinc-800/50 px-3 py-2 text-sm text-white"
                >
                  <option value="researcher">Researcher</option>
                  <option value="faculty">Faculty</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <Button
                onClick={handleSave}
                disabled={saving}
                className="bg-emerald-500 text-white hover:bg-emerald-600"
              >
                {saving ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                {saved ? "Saved!" : "Save Changes"}
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      <Card className="border-zinc-800 bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-white">
            <Eye className="h-5 w-5 text-zinc-400" /> Accessibility
          </CardTitle>
        </CardHeader>
        <CardContent>
          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              checked={highContrast}
              onChange={toggleHighContrast}
              className="mt-1 h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-emerald-500"
            />
            <div className="flex-1">
              <div className="text-sm font-medium text-white">
                High Contrast Mode
              </div>
              <p className="mt-1 text-sm text-zinc-400">
                WCAG 2.1 AAA palette optimized for projector presentations and
                low-vision readers. Toggle anywhere with{" "}
                <kbd className="rounded border border-zinc-700 bg-zinc-800 px-1.5 py-0.5 font-mono text-xs text-zinc-300">
                  Alt + H
                </kbd>
                .
              </p>
            </div>
          </label>
        </CardContent>
      </Card>

      <Card className="border-zinc-800 bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-white">
            <Bell className="h-5 w-5 text-zinc-400" /> Notification Preferences
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {[
            { label: "Email me when a source check completes", checked: true },
            { label: "Email me when a researcher analysis completes", checked: true },
            { label: "Weekly digest of activity", checked: false },
          ].map((pref) => (
            <label key={pref.label} className="flex items-center gap-3 text-sm text-zinc-300">
              <input
                type="checkbox"
                defaultChecked={pref.checked}
                className="h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-emerald-500"
              />
              {pref.label}
            </label>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
