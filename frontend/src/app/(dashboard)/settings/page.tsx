"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useSession, signOut } from "next-auth/react";
import {
  AlertTriangle,
  BarChart3,
  Bell,
  Download,
  Globe,
  Loader2,
  Lock,
  Save,
  Sun,
  User as UserIcon,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useColorMode } from "@/contexts/ColorModeContext";
import { useTheme } from "@/contexts/ThemeContext";
import { apiFetch } from "@/lib/api";

// ─── Types ─────────────────────────────────────────────────────────────────

interface ProfileResponse {
  id: string;
  email: string;
  full_name: string;
  institution: string | null;
  role: string;
  tier: string;
  locale: string;
  deactivated_at: string | null;
  created_at: string;
}

interface NotificationPrefs {
  email_on_completion: boolean;
  email_on_low_credibility: boolean;
  email_weekly_digest: boolean;
  email_product_updates: boolean;
}

interface UsageBucket {
  used: number;
  limit: number | null;
  percent: number | null;
}

interface UsageResponse {
  tier: string;
  period_start: string;
  period_end: string;
  usage: {
    source_checks: UsageBucket;
    researcher_analyses: UsageBucket;
    reports: UsageBucket;
  };
}

const LOCALE_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "en", label: "English (en)" },
  { value: "az", label: "Azərbaycan (az)" },
  { value: "ru", label: "Русский (ru)" },
];

// ─── Page ──────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [profileError, setProfileError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const res = await apiFetch("/api/auth/me", { signal: controller.signal });
        if (!res.ok) {
          setProfileError(`Failed to load profile (HTTP ${res.status})`);
          return;
        }
        setProfile((await res.json()) as ProfileResponse);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setProfileError("Failed to load profile");
      } finally {
        setLoadingProfile(false);
      }
    })();
    return () => controller.abort();
  }, []);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">Settings</h1>
        <p className="text-zinc-600 dark:text-zinc-400">
          Manage your profile and preferences.
        </p>
      </div>

      <ProfileSection
        profile={profile}
        loading={loadingProfile}
        loadError={profileError}
        onProfileUpdate={(p) => setProfile(p)}
      />

      <NotificationsSection />

      <SecuritySection />

      <ThemeSection />

      <LanguageSection initialLocale={profile?.locale ?? "en"} />

      <UsageSection />

      <DataExportSection />

      <DangerZoneSection />
    </div>
  );
}

// ─── Profile ───────────────────────────────────────────────────────────────

function ProfileSection({
  profile,
  loading,
  loadError,
  onProfileUpdate,
}: {
  profile: ProfileResponse | null;
  loading: boolean;
  loadError: string | null;
  onProfileUpdate: (p: ProfileResponse) => void;
}) {
  const { data: session } = useSession();

  const [fullName, setFullName] = useState("");
  const [institution, setInstitution] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!profile) return;
    setFullName(profile.full_name || "");
    setInstitution(profile.institution || "");
  }, [profile]);

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
        setError((data as { detail?: string }).detail || "Failed to save profile");
        return;
      }
      const updated = (await res.json()) as ProfileResponse;
      onProfileUpdate(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 4000);
    } catch {
      setError("Network error — please try again");
    } finally {
      setSaving(false);
    }
  }

  const role = profile?.role ?? "researcher";
  const email = profile?.email ?? session?.user?.email ?? "";

  return (
    <SectionCard
      icon={<UserIcon className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />}
      title="Profile"
    >
      {loading ? (
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
          {(loadError || error) && (
            <InlineError>{loadError || error}</InlineError>
          )}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label
                htmlFor="settings-full-name"
                className="text-zinc-700 dark:text-zinc-300"
              >
                Full Name
              </Label>
              <Input
                id="settings-full-name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="border-zinc-300 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
              />
            </div>
            <div className="space-y-2">
              <Label
                htmlFor="settings-email"
                className="text-zinc-700 dark:text-zinc-300"
              >
                Email
              </Label>
              <Input
                id="settings-email"
                value={email}
                disabled
                className="border-zinc-300 bg-zinc-50 text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-500"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label
              htmlFor="settings-institution"
              className="text-zinc-700 dark:text-zinc-300"
            >
              Institution / University
            </Label>
            <Input
              id="settings-institution"
              value={institution}
              onChange={(e) => setInstitution(e.target.value)}
              placeholder="e.g. ADA University"
              className="border-zinc-300 bg-white text-zinc-900 placeholder:text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white dark:placeholder:text-zinc-500"
            />
          </div>
          {/* Role is read-only — privileged changes go through an admin tool. */}
          <div className="space-y-2">
            <Label
              htmlFor="settings-role"
              className="text-zinc-700 dark:text-zinc-300"
            >
              Role
            </Label>
            <Input
              id="settings-role"
              value={role.charAt(0).toUpperCase() + role.slice(1)}
              disabled
              className="border-zinc-300 bg-zinc-50 text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-500"
            />
          </div>
          <Button
            onClick={handleSave}
            disabled={saving || !!loadError}
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
    </SectionCard>
  );
}

// ─── Notifications ─────────────────────────────────────────────────────────

const NOTIFICATION_LABELS: Record<keyof NotificationPrefs, { label: string; help: string }> =
  {
    email_on_completion: {
      label: "Source check completed",
      help: "When a source verification finishes processing.",
    },
    email_on_low_credibility: {
      label: "Low credibility alerts",
      help: "When a finished check scores below the alert threshold.",
    },
    email_weekly_digest: {
      label: "Weekly digest",
      help: "A Monday-morning summary of your week's checks.",
    },
    email_product_updates: {
      label: "Product updates",
      help: "Major new features and platform changes.",
    },
  };

function NotificationsSection() {
  const [prefs, setPrefs] = useState<NotificationPrefs | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const res = await apiFetch("/api/auth/me/notifications", {
          signal: controller.signal,
        });
        if (!res.ok) {
          setError(`Failed to load preferences (HTTP ${res.status})`);
          return;
        }
        setPrefs((await res.json()) as NotificationPrefs);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError("Failed to load preferences");
      } finally {
        setLoading(false);
      }
    })();
    return () => controller.abort();
  }, []);

  async function persist(next: NotificationPrefs) {
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/api/auth/me/notifications", {
        method: "PUT",
        body: JSON.stringify(next),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError((data as { detail?: string }).detail || "Failed to save preferences");
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

  function toggle(key: keyof NotificationPrefs) {
    if (!prefs) return;
    const next = { ...prefs, [key]: !prefs[key] };
    setPrefs(next);
    void persist(next);
  }

  return (
    <SectionCard
      icon={<Bell className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />}
      title="Notifications"
      action={
        saved ? (
          <span className="text-xs text-emerald-700 dark:text-emerald-400">Saved</span>
        ) : saving ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-400" />
        ) : null
      }
    >
      {loading ? (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-10 animate-pulse rounded-md bg-zinc-200/70 dark:bg-zinc-800/60"
            />
          ))}
        </div>
      ) : (
        <>
          {error && <InlineError>{error}</InlineError>}
          <div className="space-y-1">
            {(Object.keys(NOTIFICATION_LABELS) as Array<keyof NotificationPrefs>).map(
              (key) => {
                const meta = NOTIFICATION_LABELS[key];
                const value = prefs?.[key] ?? false;
                const inputId = `notif-${key}`;
                return (
                  <div
                    key={key}
                    className="flex items-start justify-between gap-4 rounded-lg px-3 py-2.5 hover:bg-zinc-50 dark:hover:bg-zinc-800/40"
                  >
                    <div className="min-w-0 flex-1">
                      <Label
                        htmlFor={inputId}
                        className="cursor-pointer text-sm font-medium text-zinc-900 dark:text-white"
                      >
                        {meta.label}
                      </Label>
                      <p className="mt-0.5 text-xs text-zinc-600 dark:text-zinc-400">
                        {meta.help}
                      </p>
                    </div>
                    <ToggleSwitch
                      id={inputId}
                      checked={value}
                      onChange={() => toggle(key)}
                      ariaLabel={meta.label}
                    />
                  </div>
                );
              }
            )}
          </div>
          <p className="mt-3 text-xs italic text-zinc-500 dark:text-zinc-400">
            Email delivery is not yet wired up — preferences are stored for when it lands.
          </p>
        </>
      )}
    </SectionCard>
  );
}

// ─── Security ──────────────────────────────────────────────────────────────

function SecuritySection() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  function reset() {
    setCurrent("");
    setNext("");
    setConfirm("");
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setSuccess(false);

    if (next.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (next !== confirm) {
      setError("New password and confirmation do not match.");
      return;
    }
    if (next === current) {
      setError("New password must differ from the current one.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await apiFetch("/api/auth/me/change-password", {
        method: "POST",
        skipAuthRedirect: true,
        body: JSON.stringify({
          current_password: current,
          new_password: next,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = (data as { detail?: string }).detail;
        if (detail && detail.includes("Google sign-in")) {
          setInfo(detail);
        } else {
          setError(detail || `Failed to change password (HTTP ${res.status})`);
        }
        return;
      }
      reset();
      setSuccess(true);
      setTimeout(() => setSuccess(false), 4000);
    } catch {
      setError("Network error — please try again");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SectionCard
      icon={<Lock className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />}
      title="Security"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <InlineError>{error}</InlineError>}
        {info && (
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-700 dark:border-zinc-800 dark:bg-zinc-800/40 dark:text-zinc-300">
            {info}
          </div>
        )}
        {success && (
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-400">
            Password changed.
          </div>
        )}
        <div className="space-y-2">
          <Label
            htmlFor="security-current"
            className="text-zinc-700 dark:text-zinc-300"
          >
            Current password
          </Label>
          <Input
            id="security-current"
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            className="border-zinc-300 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
          />
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label
              htmlFor="security-new"
              className="text-zinc-700 dark:text-zinc-300"
            >
              New password
            </Label>
            <Input
              id="security-new"
              type="password"
              autoComplete="new-password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              className="border-zinc-300 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
            />
          </div>
          <div className="space-y-2">
            <Label
              htmlFor="security-confirm"
              className="text-zinc-700 dark:text-zinc-300"
            >
              Confirm new password
            </Label>
            <Input
              id="security-confirm"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="border-zinc-300 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
            />
          </div>
        </div>
        <Button
          type="submit"
          disabled={submitting || !current || !next || !confirm}
          className="bg-brand text-white hover:bg-brand-hover"
        >
          {submitting ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Lock className="mr-2 h-4 w-4" />
          )}
          Change Password
        </Button>
      </form>
    </SectionCard>
  );
}

// ─── Theme ─────────────────────────────────────────────────────────────────

function ThemeSection() {
  const { mode, setMode } = useColorMode();
  const { highContrast, toggleHighContrast } = useTheme();

  const options: ReadonlyArray<{ value: "system" | "light" | "dark"; label: string }> = [
    { value: "system", label: "System" },
    { value: "light", label: "Light" },
    { value: "dark", label: "Dark" },
  ];

  return (
    <SectionCard
      icon={<Sun className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />}
      title="Theme"
    >
      <div
        role="radiogroup"
        aria-label="Color mode"
        className="grid grid-cols-3 gap-2"
      >
        {options.map((opt) => {
          const active = mode === opt.value;
          const id = `theme-mode-${opt.value}`;
          return (
            <label
              key={opt.value}
              htmlFor={id}
              className={
                "flex cursor-pointer items-center justify-center rounded-lg border px-3 py-2 text-sm font-medium transition-colors " +
                (active
                  ? "border-brand bg-brand/10 text-brand dark:border-brand dark:bg-brand/15 dark:text-brand-fg"
                  : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-300 dark:hover:border-zinc-700")
              }
            >
              <input
                id={id}
                type="radio"
                name="theme-mode"
                value={opt.value}
                checked={active}
                onChange={() => setMode(opt.value)}
                className="sr-only"
              />
              {opt.label}
            </label>
          );
        })}
      </div>

      <div className="mt-5 border-t border-zinc-200 pt-4 dark:border-zinc-800">
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
      </div>
    </SectionCard>
  );
}

// ─── Language ──────────────────────────────────────────────────────────────

function LanguageSection({ initialLocale }: { initialLocale: string }) {
  const [locale, setLocale] = useState(initialLocale);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLocale(initialLocale);
  }, [initialLocale]);

  async function handleChange(next: string) {
    if (next === locale) return;
    const previous = locale;
    setLocale(next);
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/api/auth/me/locale", {
        method: "PUT",
        body: JSON.stringify({ locale: next }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError((data as { detail?: string }).detail || "Failed to save language");
        setLocale(previous);
        return;
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setError("Network error — please try again");
      setLocale(previous);
    } finally {
      setSaving(false);
    }
  }

  return (
    <SectionCard
      icon={<Globe className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />}
      title="Language"
      action={
        saved ? (
          <span className="text-xs text-emerald-700 dark:text-emerald-400">Saved</span>
        ) : saving ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-400" />
        ) : null
      }
    >
      {error && <InlineError>{error}</InlineError>}
      <div className="space-y-2">
        <Label
          htmlFor="settings-locale"
          className="text-zinc-700 dark:text-zinc-300"
        >
          Interface language
        </Label>
        <select
          id="settings-locale"
          value={locale}
          onChange={(e) => handleChange(e.target.value)}
          disabled={saving}
          className="block h-9 w-full rounded-lg border border-zinc-300 bg-white px-2.5 text-sm text-zinc-900 outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
        >
          {LOCALE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
      <p className="mt-3 text-xs italic text-zinc-500 dark:text-zinc-400">
        UI translation lands in a future release — for now this just saves your preference.
      </p>
    </SectionCard>
  );
}

// ─── Usage ─────────────────────────────────────────────────────────────────

function UsageSection() {
  const [usage, setUsage] = useState<UsageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const res = await apiFetch("/api/dashboard/usage", {
          signal: controller.signal,
        });
        if (!res.ok) {
          setError(`Failed to load usage (HTTP ${res.status})`);
          return;
        }
        setUsage((await res.json()) as UsageResponse);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setError("Failed to load usage");
      } finally {
        setLoading(false);
      }
    })();
    return () => controller.abort();
  }, []);

  const rows: Array<{ key: keyof UsageResponse["usage"]; label: string }> = [
    { key: "source_checks", label: "Source checks" },
    { key: "researcher_analyses", label: "Researcher analyses" },
    { key: "reports", label: "Reports" },
  ];

  return (
    <SectionCard
      icon={<BarChart3 className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />}
      title="Usage this month"
    >
      {loading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-10 animate-pulse rounded-md bg-zinc-200/70 dark:bg-zinc-800/60"
            />
          ))}
        </div>
      ) : error ? (
        <InlineError>{error}</InlineError>
      ) : usage ? (
        <div className="space-y-4">
          {rows.map((row) => (
            <UsageRow
              key={row.key}
              label={row.label}
              bucket={usage.usage[row.key]}
            />
          ))}
        </div>
      ) : null}
    </SectionCard>
  );
}

function UsageRow({ label, bucket }: { label: string; bucket: UsageBucket }) {
  const unlimited = bucket.limit === null;
  // Spec says percent === 100 paints red; otherwise amber from 75 onwards.
  const percent = bucket.percent ?? 0;
  let barClass = "bg-brand";
  if (!unlimited) {
    if (percent === 100) barClass = "bg-red-500";
    else if (percent >= 75) barClass = "bg-accent-amber";
  }

  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium text-zinc-900 dark:text-white">
          {label}
        </span>
        {unlimited ? (
          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-400">
            Unlimited
          </span>
        ) : (
          <span className="tnum text-sm text-zinc-600 dark:text-zinc-400">
            <span className="font-semibold text-zinc-900 dark:text-white">
              {bucket.used}
            </span>{" "}
            / {bucket.limit}
          </span>
        )}
      </div>
      {!unlimited && (
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
          <div
            className={`h-full rounded-full transition-all ${barClass}`}
            style={{ width: `${Math.min(100, percent)}%` }}
            role="progressbar"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${label} usage`}
          />
        </div>
      )}
    </div>
  );
}

// ─── Data export ───────────────────────────────────────────────────────────

function DataExportSection() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleExport() {
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch("/api/auth/me/export");
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(
          (data as { detail?: string }).detail ||
            `Export failed (HTTP ${res.status})`
        );
        return;
      }
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const filename =
        parseFilename(res.headers.get("Content-Disposition")) ||
        `artiproof-export-${new Date().toISOString().slice(0, 10)}.zip`;
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objectUrl);
    } catch {
      setError("Network error — please try again");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SectionCard
      icon={<Download className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />}
      title="Data export"
    >
      <p className="mb-4 text-sm text-zinc-600 dark:text-zinc-400">
        Download every record we hold for your account — profile, source checks,
        researcher analyses, and report metadata — as a single archive.
      </p>
      {error && <InlineError>{error}</InlineError>}
      <Button
        onClick={handleExport}
        disabled={busy}
        className="bg-brand text-white hover:bg-brand-hover"
      >
        {busy ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Exporting...
          </>
        ) : (
          <>
            <Download className="mr-2 h-4 w-4" /> Download account export (.zip)
          </>
        )}
      </Button>
    </SectionCard>
  );
}

function parseFilename(header: string | null): string | null {
  if (!header) return null;
  const match = /filename="?([^";]+)"?/i.exec(header);
  return match ? match[1] : null;
}

// ─── Danger zone ───────────────────────────────────────────────────────────

function DangerZoneSection() {
  const [deactivateOpen, setDeactivateOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  return (
    <Card className="border-red-300/60 bg-white dark:border-red-900/50 dark:bg-zinc-900/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-white">
          <AlertTriangle
            className="h-5 w-5 text-red-600 dark:text-red-400"
            aria-hidden="true"
          />
          Danger zone
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <DangerRow
          warningId="danger-deactivate-warn"
          title="Deactivate account"
          warning="Suspends the account. You can reactivate by signing back in. While deactivated, all routes return 423 except sign-in and reactivation."
          buttonLabel="Deactivate"
          onClick={() => setDeactivateOpen(true)}
          buttonClass="bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
        />
        <div className="border-t border-zinc-200 dark:border-zinc-800" />
        <DangerRow
          warningId="danger-delete-warn"
          title="Delete account"
          warning="Soft-deletes your account and every owned source check, researcher analysis, and report. The cleanup task hard-deletes everything after a 30-day grace window. You will be signed out immediately."
          buttonLabel="Delete account"
          onClick={() => setDeleteOpen(true)}
          buttonClass="bg-red-600 text-white hover:bg-red-700"
        />
      </CardContent>

      <DeactivateDialog open={deactivateOpen} onOpenChange={setDeactivateOpen} />
      <DeleteDialog open={deleteOpen} onOpenChange={setDeleteOpen} />
    </Card>
  );
}

function DangerRow({
  warningId,
  title,
  warning,
  buttonLabel,
  onClick,
  buttonClass,
}: {
  warningId: string;
  title: string;
  warning: string;
  buttonLabel: string;
  onClick: () => void;
  buttonClass: string;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-zinc-900 dark:text-white">{title}</p>
        <p
          id={warningId}
          className="mt-1 text-sm text-zinc-600 dark:text-zinc-400"
        >
          {warning}
        </p>
      </div>
      <button
        type="button"
        onClick={onClick}
        aria-describedby={warningId}
        className={`shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50 ${buttonClass}`}
      >
        {buttonLabel}
      </button>
    </div>
  );
}

function DeactivateDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
}) {
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setPassword("");
      setError(null);
    }
  }, [open]);

  async function handleDeactivate() {
    setSubmitting(true);
    setError(null);
    try {
      const res = await apiFetch("/api/auth/me/deactivate", {
        method: "POST",
        skipAuthRedirect: true,
        body: JSON.stringify({ current_password: password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(
          (data as { detail?: string }).detail ||
            `Failed to deactivate (HTTP ${res.status})`
        );
        return;
      }
      // Deactivated accounts get 423 on every route except /me and reactivate;
      // sign out to avoid leaving a half-broken session in the browser.
      await signOut({ callbackUrl: "/login" });
    } catch {
      setError("Network error — please try again");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Deactivate account</DialogTitle>
          <DialogDescription>
            Confirm with your current password. You can sign back in at any
            time to reactivate.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {error && <InlineError>{error}</InlineError>}
          <div className="space-y-2">
            <Label
              htmlFor="deactivate-password"
              className="text-zinc-700 dark:text-zinc-300"
            >
              Current password
            </Label>
            <Input
              id="deactivate-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="border-zinc-300 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
            />
          </div>
        </div>
        <DialogFooter>
          <DialogClose
            render={
              <Button variant="outline" disabled={submitting}>
                Cancel
              </Button>
            }
          />
          <Button
            type="button"
            onClick={handleDeactivate}
            disabled={submitting || !password}
            className="bg-zinc-900 text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
          >
            {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Deactivate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DeleteDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
}) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setPassword("");
      setConfirm("");
      setError(null);
    }
  }, [open]);

  async function handleDelete() {
    setSubmitting(true);
    setError(null);
    try {
      const res = await apiFetch("/api/auth/me", {
        method: "DELETE",
        skipAuthRedirect: true,
        body: JSON.stringify({ current_password: password, confirm }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(
          (data as { detail?: string }).detail ||
            `Failed to delete account (HTTP ${res.status})`
        );
        return;
      }
      await signOut({ callbackUrl: "/login" });
    } catch {
      setError("Network error — please try again");
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = password.length > 0 && confirm === "DELETE";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete account</DialogTitle>
          <DialogDescription>
            This action soft-deletes your account and every owned record. The
            cleanup task hard-deletes everything after 30 days.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {error && <InlineError>{error}</InlineError>}
          <div className="space-y-2">
            <Label
              htmlFor="delete-password"
              className="text-zinc-700 dark:text-zinc-300"
            >
              Current password
            </Label>
            <Input
              id="delete-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="border-zinc-300 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
            />
          </div>
          <div className="space-y-2">
            <Label
              htmlFor="delete-confirm"
              className="text-zinc-700 dark:text-zinc-300"
            >
              Type{" "}
              <span className="font-mono font-semibold text-red-600 dark:text-red-400">
                DELETE
              </span>{" "}
              to confirm
            </Label>
            <Input
              id="delete-confirm"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="off"
              className="border-zinc-300 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
            />
          </div>
        </div>
        <DialogFooter>
          <DialogClose
            render={
              <Button variant="outline" disabled={submitting}>
                Cancel
              </Button>
            }
          />
          <Button
            type="button"
            onClick={handleDelete}
            disabled={submitting || !canSubmit}
            className="bg-red-600 text-white hover:bg-red-700"
          >
            {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Delete account
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Shared bits ───────────────────────────────────────────────────────────

function SectionCard({
  icon,
  title,
  action,
  children,
}: {
  icon: ReactNode;
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card className="border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/50">
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-white">
            {icon}
            {title}
          </CardTitle>
          {action}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}

function InlineError({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-400"
    >
      {children}
    </div>
  );
}

function ToggleSwitch({
  id,
  checked,
  onChange,
  ariaLabel,
}: {
  id: string;
  checked: boolean;
  onChange: () => void;
  ariaLabel: string;
}) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      onClick={onChange}
      className={
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-zinc-900 " +
        (checked
          ? "bg-brand"
          : "bg-zinc-300 dark:bg-zinc-700")
      }
    >
      <span
        aria-hidden="true"
        className={
          "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform " +
          (checked ? "translate-x-4" : "translate-x-0.5")
        }
      />
    </button>
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
