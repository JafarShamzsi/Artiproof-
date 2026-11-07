"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { User, Save, Loader2, Eye } from "lucide-react";
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
    // AbortController so a navigation away cancels the in-flight fetch
    // *and* prevents the catch from misclassifying the abort as an error.
    const controller = new AbortController();
    (async () => {
      try {
        const res = await apiFetch("/api/auth/me", { signal: controller.signal });
        if (!res.ok) {
          setError(`Failed to load profile (HTTP ${res.status})`);
          return;
        }
        const profile = (await res.json()) as ProfileResponse;
        setFullName(profile.full_name || "");
        setInstitution(profile.institution || "");
        setRole((profile.role as UserRole) || "researcher");
        setEmail(profile.email);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError("Failed to load profile");
      } finally {
        setLoadingProfile(false);
      }
    })();
    return () => controller.abort();
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
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Failed to save profile");
        return;
      }

      setSaved(true);
      // 2s is too short to actually read on a quick save; 4s is generous
      setTimeout(() => setSaved(false), 4000);
    } catch {
      setError("Network error — please try again");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">Settings</h1>
        <p className="text-zinc-600 dark:text-zinc-400">Manage your profile and preferences.</p>
      </div>

      <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-white">
            <User className="h-5 w-5 text-zinc-500 dark:text-zinc-400" /> Profile
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {loadingProfile ? (
            <div className="space-y-4" aria-busy="true" aria-label="Loading profile">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <SkeletonField />
                <SkeletonField />
              </div>
              <SkeletonField />
              <SkeletonField />
              <div className="h-9 w-32 animate-pulse rounded-md bg-zinc-200/70 dark:bg-zinc-800/60" />
            </div>
          ) : (
            <>
              {error && (
                <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-400">
                  {error}
                </div>
              )}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="settings-full-name" className="text-zinc-700 dark:text-zinc-300">Full Name</Label>
                  <Input
                    id="settings-full-name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="border-zinc-300 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="settings-email" className="text-zinc-700 dark:text-zinc-300">Email</Label>
                  <Input
                    id="settings-email"
                    value={email || session?.user?.email || ""}
                    disabled
                    className="border-zinc-300 bg-zinc-50 text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-500"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="settings-institution" className="text-zinc-700 dark:text-zinc-300">Institution / University</Label>
                <Input
                  id="settings-institution"
                  value={institution}
                  onChange={(e) => setInstitution(e.target.value)}
                  placeholder="e.g. ADA University"
                  className="border-zinc-300 bg-white text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white dark:placeholder:text-zinc-500"
                />
              </div>
              {/* Role is read-only — privileged changes go through an admin tool,
                  not the user's own profile editor. Display only. */}
              <div className="space-y-2">
                <Label htmlFor="settings-role" className="text-zinc-700 dark:text-zinc-300">Role</Label>
                <Input
                  id="settings-role"
                  value={role.charAt(0).toUpperCase() + role.slice(1)}
                  disabled
                  className="border-zinc-300 bg-zinc-50 text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-500"
                />
              </div>
              <Button
                onClick={handleSave}
                disabled={saving}
                className="bg-brand text-white hover:bg-brand-hover"
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

      <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-white">
            <Eye className="h-5 w-5 text-zinc-500 dark:text-zinc-400" /> Accessibility
          </CardTitle>
        </CardHeader>
        <CardContent>
          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              checked={highContrast}
              onChange={toggleHighContrast}
              className="mt-1 h-4 w-4 rounded border-zinc-300 bg-white text-brand dark:border-zinc-600 dark:bg-zinc-800"
            />
            <div className="flex-1">
              <div className="text-sm font-medium text-zinc-900 dark:text-white">
                High Contrast Mode
              </div>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                WCAG 2.1 AAA palette optimized for projector presentations and
                low-vision readers. Toggle anywhere with{" "}
                <kbd className="rounded border border-zinc-300 bg-zinc-100 px-1.5 py-0.5 font-mono text-xs text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                  Alt + H
                </kbd>
                .
              </p>
            </div>
          </label>
        </CardContent>
      </Card>

      {/* Notification preferences removed — checkboxes were non-functional.
          TODO: restore once the backend has a notification-prefs API. */}
    </div>
  );
}

function SkeletonField() {
  return (
    <div className="space-y-2">
      <div className="h-4 w-24 animate-pulse rounded bg-zinc-200/70 dark:bg-zinc-800/60" />
      <div className="h-9 w-full animate-pulse rounded-md bg-zinc-200/70 dark:bg-zinc-800/60" />
    </div>
  );
}
