"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { QRCodeSVG } from "qrcode.react";
import {
  AlertTriangle,
  BarChart3,
  Bell,
  CalendarClock,
  Chrome,
  Copy,
  Download,
  EyeOff,
  Globe,
  Link2,
  Loader2,
  Lock,
  LogOut,
  Mail,
  MailCheck,
  MonitorSmartphone,
  Palette,
  PlayCircle,
  Save,
  ShieldCheck,
  Sliders,
  Sun,
  Trash2,
  User as UserIcon,
  Users,
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
import { useTour } from "@/contexts/TourContext";
import { TOURS } from "@/lib/tours";
import { apiFetch } from "@/lib/api";
import { toast } from "@/lib/toast";

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
  // Team-tier privacy toggle. Defaults to true server-side.
  share_activity_with_team: boolean;
  // Null on free/pro tier.
  organization_id: string | null;
  // The user's role within their org. Null when they aren't a member
  // of any org. Used to gate admin-only buttons in the org-member
  // management section.
  org_role: "admin" | "member" | null;
  // ─── Billing scaffolding (Phase D) ──────────────────────────────────
  // "none" until a payment processor is wired. The Settings → Billing
  // section uses these to render a state badge + the next billing
  // date. No action buttons are wired yet; the placeholder explains.
  subscription_state:
    | "none"
    | "active"
    | "past_due"
    | "cancelled"
    | "paused";
  next_billing_date: string | null;
  last_billing_date: string | null;
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

interface EmailVerificationStatus {
  email: string;
  verified: boolean;
  verified_at: string | null;
}

interface EmailVerificationRequestResponse {
  detail: string;
  dev_verify_url?: string;
}

interface TotpStatus {
  enabled: boolean;
  backup_codes_remaining: number;
}

interface TotpSetupResponse {
  provisioning_uri: string;
  secret: string;
  backup_codes: string[];
}

interface SessionItem {
  id: string;
  user_agent: string | null;
  ip_address: string | null;
  label: string | null;
  created_at: string;
  last_used_at: string | null;
  is_current: boolean;
}

interface ConnectionItem {
  provider: string;
  linked: boolean;
  email: string | null;
  linked_at: string | null;
}

interface AnalysisPreferences {
  check_citations: boolean;
  trace_misinfo_origins: boolean;
  researcher_field_inference: boolean;
}

const LOCALE_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "en", label: "English (en)" },
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
        <h1 className="font-display text-2xl font-bold text-fg-primary">Settings</h1>
        <p className="text-fg-secondary">
          Manage your profile and preferences.
        </p>
      </div>

      <EmailVerificationBanner />

      <ProfileSection
        profile={profile}
        loading={loadingProfile}
        loadError={profileError}
        onProfileUpdate={(p) => setProfile(p)}
      />

      <NotificationsSection />

      {profile?.tier === "team" && (
        <PrivacySection
          initialShare={profile.share_activity_with_team}
          onProfileUpdate={(p) => setProfile(p)}
        />
      )}

      <SecuritySection />

      <ActiveSessionsSection />

      <ConnectedAccountsSection />

      <ThemeSection />

      <OnboardingTourSection />

      <LanguageSection initialLocale={profile?.locale ?? "en"} />

      <AnalysisPreferencesSection />

      <UsageSection />

      {profile && <BillingSection profile={profile} />}

      <DataExportSection />

      <ScheduledReportsSection />

      {/* Team management surface. Team-tier users with an org get a
          link card pointing at the dedicated /team workspace (which
          owns Members / Invites / Audit / org settings). The branding
          editor stays inline here because it lives close to other
          appearance-y controls users tweak from Settings.
          Free / Pro users see the upgrade card with the trial CTA. */}
      {profile?.tier === "team" && profile?.organization_id ? (
        <>
          <TeamWorkspaceLinkSection />
          <BrandingSection orgId={profile.organization_id} />
        </>
      ) : (
        profile && <TeamUpgradeSection currentTier={profile.tier} />
      )}

      <SignOutSection />

      <DangerZoneSection />
    </div>
  );
}

// ─── Sign out (this device) ────────────────────────────────────────────────
// Sits between team-management and Danger zone so a user looking for
// "where do I sign out?" finds it on the page itself instead of hunting
// for the avatar dropdown. Renamed the existing "Sign out everywhere
// else" path in ActiveSessionsSection; this one signs out the current
// device only. Two separate intents on purpose — one is "I'm leaving
// this laptop", the other is "revoke everywhere I forgot to log out".

function SignOutSection() {
  const [busy, setBusy] = useState(false);
  return (
    <SectionCard
      icon={<LogOut className="h-4 w-4" />}
      title="Sign out"
      description="Sign out of ArtiProof on this device. Other devices stay signed in — use the Active sessions list above to revoke them too."
    >
      <Button
        type="button"
        variant="outline"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          // signOut returns; the callback redirect happens client-side.
          await signOut({ callbackUrl: "/login" });
        }}
      >
        {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <LogOut className="mr-2 h-4 w-4" />}
        Sign out
      </Button>
    </SectionCard>
  );
}

// ─── Team upgrade placeholder ───────────────────────────────────────────────
// Free + pro users land in Settings and previously saw NO team management
// surface — the pricing page promises team features but the dashboard
// hid them entirely. Now we show a "Team-tier feature" card with an
// upgrade CTA so the path is discoverable.

function TeamUpgradeSection({ currentTier }: { currentTier: string }) {
  const router = useRouter();
  const { update } = useSession();
  const [open, setOpen] = useState(false);
  const [teamName, setTeamName] = useState("");
  const [creating, setCreating] = useState(false);

  // Auto-open on `?startTeam=1` arrival — pricing-page CTAs deep-link
  // straight into the trial flow without a separate "open modal" click.
  const search = useSearchParams();
  useEffect(() => {
    if (search?.get("startTeam") === "1") setOpen(true);
  }, [search]);

  async function startTrial(e: React.FormEvent) {
    e.preventDefault();
    const name = teamName.trim();
    if (!name || creating) return;
    setCreating(true);
    try {
      const res = await apiFetch("/api/organizations", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        toast.error(data.detail || "Couldn't start the trial");
        return;
      }
      const body = (await res.json()) as { id: string; name: string };
      // Refresh the NextAuth session so the dashboard layout picks up
      // the new tier + org id without a forced re-login. The jwt
      // callback merges these into the token.
      await update({ tier: "team", organizationId: body.id });
      toast.success(`Welcome to ${body.name} — 14-day trial started.`);
      setOpen(false);
      router.push("/team");
      router.refresh();
    } finally {
      setCreating(false);
    }
  }

  return (
    <SectionCard
      icon={<Users className="h-4 w-4" />}
      title="Team & members"
      description="Invite collaborators, manage roles, and share organisation-wide branding on reports."
    >
      <div className="rounded-lg border border-dashed border-border-default bg-brand-soft/50 p-4">
        <p className="text-sm font-medium text-fg-primary">
          Team management is a Team-tier feature.
        </p>
        <p className="mt-1 text-xs text-fg-secondary">
          You&rsquo;re on the {currentTier} plan. Start a free 14-day trial to
          invite teammates, manage roles, and pool report exports — no card
          required.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            type="button"
            onClick={() => setOpen(true)}
            className="bg-brand text-white hover:bg-brand-hover"
          >
            Start 14-day trial
          </Button>
          <Link
            href="/pricing#team"
            className="inline-flex h-9 items-center rounded-lg border border-border-default px-4 text-sm font-medium text-fg-primary transition-colors hover:bg-brand-soft"
          >
            See Team pricing
          </Link>
          <Link
            href="/contact-sales?plan=institution"
            className="inline-flex h-9 items-center rounded-lg border border-border-default px-4 text-sm font-medium text-fg-primary transition-colors hover:bg-brand-soft"
          >
            Contact sales
          </Link>
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="border-border-default bg-surface-card">
          <DialogHeader>
            <DialogTitle>Start a Team trial</DialogTitle>
            <DialogDescription>
              We&rsquo;ll create a team workspace under your account. You can
              rename or delete it anytime during the 14-day trial.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={startTrial} className="space-y-4">
            <div>
              <Label htmlFor="team-name">Team name</Label>
              <Input
                id="team-name"
                type="text"
                required
                minLength={2}
                maxLength={80}
                placeholder="e.g. Acme University Research Office"
                value={teamName}
                onChange={(e) => setTeamName(e.target.value)}
                className="mt-1"
                autoFocus
              />
            </div>
            <DialogFooter className="gap-2 sm:gap-2">
              <DialogClose
                render={
                  <Button type="button" variant="outline" disabled={creating}>
                    Cancel
                  </Button>
                }
              />
              <Button
                type="submit"
                disabled={creating || !teamName.trim()}
                className="bg-brand text-white hover:bg-brand-hover"
              >
                {creating ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : null}
                Start trial
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </SectionCard>
  );
}

// ─── Team workspace link (team-tier users) ────────────────────────────────
// The dedicated /team workspace owns Members / Invites / Audit / org
// settings. Settings keeps a small card pointing at it so a user who
// landed in Settings looking for "team management" still finds the door.

function TeamWorkspaceLinkSection() {
  return (
    <SectionCard
      icon={<Users className="h-4 w-4" />}
      title="Team & members"
      description="Members, invites, seat usage, and the audit log live in your team workspace."
    >
      <div className="flex flex-wrap items-center gap-3">
        <Link
          href="/team"
          className="inline-flex h-9 items-center rounded-lg bg-brand px-4 text-sm font-medium text-white shadow-sm shadow-brand/20 transition-colors hover:bg-brand-hover"
        >
          Open team workspace
        </Link>
        <Link
          href="/team?tab=invites"
          className="inline-flex h-9 items-center rounded-lg border border-border-default px-4 text-sm font-medium text-fg-primary transition-colors hover:bg-brand-soft"
        >
          Manage invites
        </Link>
      </div>
    </SectionCard>
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
        const msg = (data as { detail?: string }).detail || "Failed to save profile";
        // Spec: keep the inline error block on Profile (existing UX) AND
        // also fire a toast so the user gets the audible/persistent signal.
        setError(msg);
        toast.error(msg);
        return;
      }
      const updated = (await res.json()) as ProfileResponse;
      onProfileUpdate(updated);
      toast.success("Profile updated");
    } catch {
      const msg = "Network error — please try again";
      setError(msg);
      toast.error(msg);
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
            Save Changes
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
  // The load-time error is preserved as state so we can show a "couldn't
  // load" hint inline. Save-time errors are surfaced via toast only.
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const res = await apiFetch("/api/auth/me/notifications", {
          signal: controller.signal,
        });
        if (!res.ok) {
          setLoadError(`Failed to load preferences (HTTP ${res.status})`);
          return;
        }
        setPrefs((await res.json()) as NotificationPrefs);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setLoadError("Failed to load preferences");
      } finally {
        setLoading(false);
      }
    })();
    return () => controller.abort();
  }, []);

  async function persist(next: NotificationPrefs) {
    setSaving(true);
    try {
      const res = await apiFetch("/api/auth/me/notifications", {
        method: "PUT",
        body: JSON.stringify(next),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toast.error(
          (data as { detail?: string }).detail || "Failed to save preferences",
        );
        return;
      }
      toast.success("Notifications saved");
    } catch {
      toast.error("Network error — please try again");
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
        saving ? (
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
          {loadError && <InlineError>{loadError}</InlineError>}
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

// ─── Privacy (team tier) ───────────────────────────────────────────────────

function PrivacySection({
  initialShare,
  onProfileUpdate,
}: {
  initialShare: boolean;
  onProfileUpdate: (p: ProfileResponse) => void;
}) {
  const [share, setShare] = useState<boolean>(initialShare);
  const [saving, setSaving] = useState(false);

  // Keep local state in sync if the parent reloads /api/auth/me.
  useEffect(() => {
    setShare(initialShare);
  }, [initialShare]);

  async function persist(next: boolean) {
    const previous = share;
    setShare(next);
    setSaving(true);
    try {
      const res = await apiFetch("/api/auth/me/share-activity-with-team", {
        method: "PUT",
        body: JSON.stringify({ share: next }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toast.error(
          (data as { detail?: string }).detail ||
            `Failed to save (HTTP ${res.status})`,
        );
        setShare(previous);
        return;
      }
      const updated = (await res.json()) as ProfileResponse;
      onProfileUpdate(updated);
      toast.success(
        next ? "Activity sharing turned on" : "Activity sharing turned off",
      );
    } catch {
      toast.error("Network error — please try again");
      setShare(previous);
    } finally {
      setSaving(false);
    }
  }

  return (
    <SectionCard
      icon={<EyeOff className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />}
      title="Privacy"
      action={
        saving ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-400" />
        ) : null
      }
    >
      <div className="flex items-start justify-between gap-4 rounded-lg px-3 py-2.5 hover:bg-zinc-50 dark:hover:bg-zinc-800/40">
        <div className="min-w-0 flex-1">
          <Label
            htmlFor="privacy-share-activity"
            className="cursor-pointer text-sm font-medium text-zinc-900 dark:text-white"
          >
            Share my activity with my organization
          </Label>
          <p className="mt-0.5 text-xs text-zinc-600 dark:text-zinc-400">
            When on, teammates can see your source checks, researcher analyses,
            and reports in the team activity feed.
          </p>
        </div>
        <ToggleSwitch
          id="privacy-share-activity"
          checked={share}
          onChange={() => persist(!share)}
          ariaLabel="Share activity with organization"
        />
      </div>
      <p className="mt-3 text-xs italic text-zinc-500 dark:text-zinc-400">
        Your activity is visible to your organization. Turn off to keep your
        work private.
      </p>
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
      <div className="space-y-1">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-medium text-zinc-900 dark:text-white">
            Change password
          </h3>
          <Link
            href="/forgot-password"
            className="text-xs text-brand hover:text-brand-hover dark:text-brand-fg"
          >
            Forgot password?
          </Link>
        </div>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          Update the password on this account. Forgot it? Use the reset flow instead.
        </p>
      </div>
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

      <div className="border-t border-zinc-200 pt-5 dark:border-zinc-800">
        <TwoFactorSubsection />
      </div>
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

// ─── Onboarding tour ───────────────────────────────────────────────────────
// Lets the user replay the dashboard tour or any of the per-feature tours
// shipped with the platform. "Replay" wipes that tour's stored
// completion version so the auto-start logic re-fires; the manual
// "Start now" button forces it regardless of completion state.

function OnboardingTourSection() {
  const { startTour, isCompleted, resetTour } = useTour();
  const entries = Object.values(TOURS);

  return (
    <SectionCard
      icon={<PlayCircle className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />}
      title="Guided tours"
      description="Replay any of the in-product walkthroughs. New tours appear here whenever we ship a feature that needs a quick orientation."
    >
      <ul className="divide-y divide-border-default">
        {entries.map((tour) => {
          const done = isCompleted(tour.id);
          return (
            <li
              key={tour.id}
              className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-fg-primary">
                  {tour.label}
                </p>
                <p className="text-xs text-fg-secondary">
                  {tour.steps.length} steps · {done ? "Completed" : "Not yet seen"}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {done && (
                  <button
                    type="button"
                    onClick={() => resetTour(tour.id)}
                    className="text-xs text-fg-tertiary underline-offset-2 hover:text-fg-secondary hover:underline"
                  >
                    Reset
                  </button>
                )}
                <Button
                  type="button"
                  size="sm"
                  variant={done ? "outline" : "default"}
                  onClick={() => startTour(tour.id, { force: true })}
                >
                  <PlayCircle className="mr-1.5 h-4 w-4" />
                  {done ? "Replay" : "Start"}
                </Button>
              </div>
            </li>
          );
        })}
      </ul>
    </SectionCard>
  );
}

// ─── Language ──────────────────────────────────────────────────────────────

function LanguageSection({ initialLocale }: { initialLocale: string }) {
  const [locale, setLocale] = useState(initialLocale);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLocale(initialLocale);
  }, [initialLocale]);

  async function handleChange(next: string) {
    if (next === locale) return;
    const previous = locale;
    setLocale(next);
    setSaving(true);
    try {
      const res = await apiFetch("/api/auth/me/locale", {
        method: "PUT",
        body: JSON.stringify({ locale: next }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toast.error(
          (data as { detail?: string }).detail || "Failed to save language",
        );
        setLocale(previous);
        return;
      }
      toast.success("Language preference saved");
    } catch {
      toast.error("Network error — please try again");
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
        saving ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-400" />
        ) : null
      }
    >
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
        English is the only supported language right now. Additional locales return when our next-intl scaffold ships.
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

// ─── Email verification banner ─────────────────────────────────────────────

function EmailVerificationBanner() {
  const [status, setStatus] = useState<EmailVerificationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [requesting, setRequesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devUrl, setDevUrl] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const fetchStatus = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await apiFetch("/api/auth/me/email/status", { signal });
      if (!res.ok) {
        setError(`Failed to load verification status (HTTP ${res.status})`);
        return;
      }
      setStatus((await res.json()) as EmailVerificationStatus);
      setError(null);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError("Failed to load verification status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void fetchStatus(controller.signal);
    return () => controller.abort();
  }, [fetchStatus]);

  async function requestVerification() {
    setRequesting(true);
    setError(null);
    setDevUrl(null);
    setSent(false);
    try {
      const res = await apiFetch("/api/auth/me/email/verify/request", {
        method: "POST",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const msg =
          (data as { detail?: string }).detail ||
          `Failed to send link (HTTP ${res.status})`;
        // The amber banner shows the message inline (its UX is bespoke);
        // toast carries it to anyone scrolled away from this card.
        setError(msg);
        toast.error(msg);
        return;
      }
      const data = (await res.json()) as EmailVerificationRequestResponse;
      setSent(true);
      setDevUrl(data.dev_verify_url ?? null);
      toast.success("Verification link sent");
    } catch {
      const msg = "Network error — please try again";
      setError(msg);
      toast.error(msg);
    } finally {
      setRequesting(false);
    }
  }

  // Hide the banner entirely once the email is verified — there's nothing to do.
  if (loading) {
    return (
      <div className="h-20 animate-pulse rounded-lg bg-zinc-200/70 dark:bg-zinc-800/60" />
    );
  }
  if (!status || status.verified) return null;

  return (
    <Card className="border-amber-300/60 bg-amber-50/70 dark:border-amber-700/40 dark:bg-amber-950/30">
      <CardContent className="flex flex-col gap-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-900/40">
            <Mail className="h-5 w-5 text-amber-700 dark:text-amber-300" />
          </div>
          <div>
            <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
              Verify your email
            </p>
            <p className="mt-0.5 text-sm text-amber-800/80 dark:text-amber-300/80">
              {status.email} hasn&apos;t been verified yet. We&apos;ll send a confirmation link.
            </p>
            {error && (
              <p className="mt-2 text-sm text-red-700 dark:text-red-400">{error}</p>
            )}
            {sent && !devUrl && (
              <p className="mt-2 text-sm text-emerald-700 dark:text-emerald-300">
                Verification link sent. Check your inbox.
              </p>
            )}
            {devUrl && (
              <div className="mt-2 rounded-md border border-amber-300/60 bg-white/60 p-2 text-xs dark:border-amber-700/40 dark:bg-black/30">
                <p className="mb-1 font-medium text-amber-900 dark:text-amber-200">
                  Dev: open this link to verify
                </p>
                <a
                  href={devUrl}
                  className="block break-all font-mono text-amber-900 underline-offset-2 hover:underline dark:text-amber-200"
                >
                  {devUrl}
                </a>
              </div>
            )}
          </div>
        </div>
        <Button
          onClick={requestVerification}
          disabled={requesting}
          className="shrink-0 bg-brand text-white hover:bg-brand-hover"
        >
          {requesting ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <MailCheck className="mr-2 h-4 w-4" />
          )}
          {sent ? "Resend link" : "Send verification link"}
        </Button>
      </CardContent>
    </Card>
  );
}

// ─── 2FA (lives inside Security card) ──────────────────────────────────────

function TwoFactorSubsection() {
  const [status, setStatus] = useState<TotpStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [setupOpen, setSetupOpen] = useState(false);
  const [disableOpen, setDisableOpen] = useState(false);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await apiFetch("/api/auth/me/2fa", { signal });
      if (!res.ok) {
        setError(`Failed to load 2FA status (HTTP ${res.status})`);
        return;
      }
      setStatus((await res.json()) as TotpStatus);
      setError(null);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError("Failed to load 2FA status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 text-sm font-medium text-zinc-900 dark:text-white">
            <ShieldCheck className="h-4 w-4 text-zinc-500 dark:text-zinc-400" />
            Two-factor authentication
          </h3>
          {loading ? (
            <p className="mt-1 text-xs text-zinc-500">Loading…</p>
          ) : status?.enabled ? (
            <p className="mt-1 text-xs text-emerald-700 dark:text-emerald-400">
              On — {status.backup_codes_remaining} backup code
              {status.backup_codes_remaining === 1 ? "" : "s"} remaining.
            </p>
          ) : (
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              Add a one-time code from an authenticator app on top of your password.
            </p>
          )}
        </div>
        {!loading &&
          (status?.enabled ? (
            <Button
              type="button"
              variant="destructive"
              onClick={() => setDisableOpen(true)}
            >
              Disable 2FA
            </Button>
          ) : (
            <Button
              type="button"
              onClick={() => setSetupOpen(true)}
              className="bg-brand text-white hover:bg-brand-hover"
            >
              Enable 2FA
            </Button>
          ))}
      </div>
      {error && <InlineError>{error}</InlineError>}

      <TotpSetupDialog
        open={setupOpen}
        onOpenChange={(next) => {
          setSetupOpen(next);
          if (!next) void refresh();
        }}
      />
      <TotpDisableDialog
        open={disableOpen}
        onOpenChange={(next) => {
          setDisableOpen(next);
          if (!next) void refresh();
        }}
      />
    </div>
  );
}

function TotpSetupDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
}) {
  const [stage, setStage] = useState<"loading" | "scan" | "backup" | "error">(
    "loading"
  );
  const [setup, setSetup] = useState<TotpSetupResponse | null>(null);
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [secretCopied, setSecretCopied] = useState(false);
  const [codesCopied, setCodesCopied] = useState(false);

  useEffect(() => {
    if (!open) {
      setStage("loading");
      setSetup(null);
      setCode("");
      setError(null);
      setSecretCopied(false);
      setCodesCopied(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch("/api/auth/me/2fa/setup", { method: "POST" });
        if (cancelled) return;
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          setError(
            (data as { detail?: string }).detail ||
              `Failed to start 2FA setup (HTTP ${res.status})`
          );
          setStage("error");
          return;
        }
        setSetup((await res.json()) as TotpSetupResponse);
        setStage("scan");
      } catch {
        if (cancelled) return;
        setError("Network error — please try again");
        setStage("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

  async function handleEnable() {
    if (!code.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await apiFetch("/api/auth/me/2fa/enable", {
        method: "POST",
        skipAuthRedirect: true,
        body: JSON.stringify({ code: code.trim() }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(
          (data as { detail?: string }).detail ||
            `Verification failed (HTTP ${res.status})`
        );
        return;
      }
      toast.success("Two-factor authentication enabled");
      setStage("backup");
    } catch {
      setError("Network error — please try again");
    } finally {
      setSubmitting(false);
    }
  }

  async function copyText(text: string, target: "secret" | "codes") {
    try {
      await navigator.clipboard.writeText(text);
      if (target === "secret") {
        setSecretCopied(true);
        setTimeout(() => setSecretCopied(false), 2000);
      } else {
        setCodesCopied(true);
        setTimeout(() => setCodesCopied(false), 2000);
      }
    } catch {
      // Clipboard refused (no HTTPS / no user gesture). Surface visually.
      if (target === "secret") setSecretCopied(false);
      else setCodesCopied(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Enable two-factor authentication</DialogTitle>
          <DialogDescription>
            {stage === "backup"
              ? "Save your backup codes — these are shown only once."
              : "Scan the QR code in your authenticator app, then enter the 6-digit code it displays."}
          </DialogDescription>
        </DialogHeader>

        {stage === "loading" && (
          <div className="flex items-center gap-2 text-sm text-zinc-500">
            <Loader2 className="h-4 w-4 animate-spin" /> Generating secret…
          </div>
        )}

        {stage === "error" && (
          <>
            {error && <InlineError>{error}</InlineError>}
            <DialogFooter>
              <DialogClose render={<Button variant="outline">Close</Button>} />
            </DialogFooter>
          </>
        )}

        {stage === "scan" && setup && (
          <>
            {error && <InlineError>{error}</InlineError>}
            <div className="flex justify-center">
              <div className="rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-100">
                <QRCodeSVG
                  value={setup.provisioning_uri}
                  size={176}
                  level="M"
                  includeMargin={false}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label className="text-zinc-700 dark:text-zinc-300">
                Or enter this code manually
              </Label>
              <div className="flex items-center gap-2">
                <code className="flex-1 break-all rounded-md border border-zinc-200 bg-zinc-50 px-2 py-1.5 font-mono text-xs text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">
                  {setup.secret}
                </code>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void copyText(setup.secret, "secret")}
                  aria-label="Copy secret"
                >
                  <Copy className="mr-1.5 h-3.5 w-3.5" />
                  {secretCopied ? "Copied" : "Copy"}
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label
                htmlFor="totp-enable-code"
                className="text-zinc-700 dark:text-zinc-300"
              >
                Enter the 6-digit code from your authenticator app
              </Label>
              <Input
                id="totp-enable-code"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{6}"
                maxLength={6}
                placeholder="123456"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="border-zinc-300 bg-white font-mono text-lg tracking-widest text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
              />
            </div>
            <DialogFooter>
              <DialogClose
                render={<Button variant="outline" disabled={submitting}>Cancel</Button>}
              />
              <Button
                type="button"
                onClick={handleEnable}
                disabled={submitting || code.trim().length !== 6}
                className="bg-brand text-white hover:bg-brand-hover"
              >
                {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Verify and enable
              </Button>
            </DialogFooter>
          </>
        )}

        {stage === "backup" && setup && (
          <>
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-800 dark:border-amber-700/40 dark:bg-amber-900/20 dark:text-amber-300">
              Save these somewhere safe — they&apos;re your way back in if you lose
              your authenticator. Each code works once.
            </div>
            <pre className="overflow-auto rounded-md border border-zinc-200 bg-zinc-50 p-3 font-mono text-xs leading-6 text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">
              {setup.backup_codes.join("\n")}
            </pre>
            <Button
              type="button"
              variant="outline"
              onClick={() =>
                void copyText(setup.backup_codes.join("\n"), "codes")
              }
            >
              <Copy className="mr-2 h-3.5 w-3.5" />
              {codesCopied ? "Copied to clipboard" : "Copy all to clipboard"}
            </Button>
            <DialogFooter>
              <DialogClose
                render={
                  <Button className="bg-brand text-white hover:bg-brand-hover">
                    Done
                  </Button>
                }
              />
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function TotpDisableDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
}) {
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setPassword("");
      setCode("");
      setError(null);
    }
  }, [open]);

  async function handleDisable() {
    setSubmitting(true);
    setError(null);
    try {
      const res = await apiFetch("/api/auth/me/2fa/disable", {
        method: "POST",
        skipAuthRedirect: true,
        body: JSON.stringify({
          current_password: password,
          code: code.trim(),
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(
          (data as { detail?: string }).detail ||
            `Failed to disable 2FA (HTTP ${res.status})`
        );
        return;
      }
      toast.success("Two-factor authentication disabled");
      onOpenChange(false);
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
          <DialogTitle>Disable two-factor authentication</DialogTitle>
          <DialogDescription>
            Confirm with your password and a current 2FA or backup code. After
            this, your account will only require a password to sign in.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {error && <InlineError>{error}</InlineError>}
          <div className="space-y-2">
            <Label
              htmlFor="totp-disable-password"
              className="text-zinc-700 dark:text-zinc-300"
            >
              Current password
            </Label>
            <Input
              id="totp-disable-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="border-zinc-300 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
            />
          </div>
          <div className="space-y-2">
            <Label
              htmlFor="totp-disable-code"
              className="text-zinc-700 dark:text-zinc-300"
            >
              Current 2FA or backup code
            </Label>
            <Input
              id="totp-disable-code"
              autoComplete="one-time-code"
              maxLength={12}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="border-zinc-300 bg-white font-mono tracking-widest text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
            />
          </div>
        </div>
        <DialogFooter>
          <DialogClose
            render={<Button variant="outline" disabled={submitting}>Cancel</Button>}
          />
          <Button
            type="button"
            variant="destructive"
            onClick={handleDisable}
            disabled={submitting || !password || !code.trim()}
          >
            {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Disable 2FA
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Active sessions ───────────────────────────────────────────────────────

function ActiveSessionsSection() {
  const [sessions, setSessions] = useState<SessionItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [revokingAll, setRevokingAll] = useState(false);
  const [confirmAllOpen, setConfirmAllOpen] = useState(false);

  const fetchSessions = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await apiFetch("/api/auth/me/sessions", { signal });
      if (!res.ok) {
        setLoadError(`Failed to load sessions (HTTP ${res.status})`);
        return;
      }
      setSessions((await res.json()) as SessionItem[]);
      setLoadError(null);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setLoadError("Failed to load sessions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void fetchSessions(controller.signal);
    return () => controller.abort();
  }, [fetchSessions]);

  async function revokeOne(id: string) {
    setRevokingId(id);
    try {
      const res = await apiFetch(`/api/auth/me/sessions/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toast.error(
          (data as { detail?: string }).detail ||
            `Failed to revoke session (HTTP ${res.status})`,
        );
        return;
      }
      toast.success("Session revoked");
      await fetchSessions();
    } catch {
      toast.error("Network error — please try again");
    } finally {
      setRevokingId(null);
    }
  }

  async function revokeOthers() {
    setRevokingAll(true);
    try {
      const res = await apiFetch("/api/auth/me/sessions", { method: "DELETE" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toast.error(
          (data as { detail?: string }).detail ||
            `Failed to revoke sessions (HTTP ${res.status})`,
        );
        return;
      }
      toast.success("Other sessions signed out");
      setConfirmAllOpen(false);
      await fetchSessions();
    } catch {
      toast.error("Network error — please try again");
    } finally {
      setRevokingAll(false);
    }
  }

  return (
    <SectionCard
      icon={<MonitorSmartphone className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />}
      title="Active sessions"
    >
      {loading ? (
        <div className="space-y-2">
          {[0, 1].map((i) => (
            <div
              key={i}
              className="h-14 animate-pulse rounded-md bg-zinc-200/70 dark:bg-zinc-800/60"
            />
          ))}
        </div>
      ) : (
        <>
          {loadError && <InlineError>{loadError}</InlineError>}
          {sessions && sessions.length > 0 ? (
            <ul className="divide-y divide-zinc-200 overflow-hidden rounded-lg border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
              {sessions.map((s) => (
                <li
                  key={s.id}
                  className="flex flex-col gap-2 px-3 py-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-zinc-900 dark:text-white">
                      {s.user_agent || "Unknown device"}
                    </p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      {s.ip_address ? `${s.ip_address} · ` : ""}
                      {s.last_used_at
                        ? `last used ${formatRelativeTime(s.last_used_at)}`
                        : "never used"}
                    </p>
                  </div>
                  {s.is_current ? (
                    <span className="shrink-0 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-400">
                      Current session
                    </span>
                  ) : (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={revokingId === s.id}
                      onClick={() => void revokeOne(s.id)}
                      className="shrink-0"
                    >
                      {revokingId === s.id ? (
                        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                      ) : null}
                      Revoke
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              No active sessions found.
            </p>
          )}
          {sessions && sessions.length > 1 && (
            <div className="pt-1">
              <Button
                type="button"
                variant="outline"
                onClick={() => setConfirmAllOpen(true)}
              >
                Sign out everywhere else
              </Button>
            </div>
          )}
        </>
      )}

      <Dialog open={confirmAllOpen} onOpenChange={setConfirmAllOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Sign out everywhere else?</DialogTitle>
            <DialogDescription>
              This revokes every session except the one you&apos;re using now.
              Other devices will need to sign in again.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose
              render={<Button variant="outline" disabled={revokingAll}>Cancel</Button>}
            />
            <Button
              type="button"
              onClick={() => void revokeOthers()}
              disabled={revokingAll}
              className="bg-brand text-white hover:bg-brand-hover"
            >
              {revokingAll && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Sign out other sessions
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </SectionCard>
  );
}

function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "recently";
  const diff = Date.now() - then;
  const seconds = Math.round(diff / 1000);
  if (seconds < 60) return seconds <= 5 ? "just now" : `${seconds} seconds ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  const months = Math.round(days / 30);
  if (months < 12) return `${months} month${months === 1 ? "" : "s"} ago`;
  const years = Math.round(months / 12);
  return `${years} year${years === 1 ? "" : "s"} ago`;
}

// ─── Connected accounts ────────────────────────────────────────────────────

function ConnectedAccountsSection() {
  const [items, setItems] = useState<ConnectionItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [working, setWorking] = useState<string | null>(null);
  const [unlinkConfirm, setUnlinkConfirm] = useState<ConnectionItem | null>(null);

  const fetchConnections = useCallback(async (signal?: AbortSignal) => {
    try {
      const res = await apiFetch("/api/auth/me/connections", { signal });
      if (!res.ok) {
        setLoadError(`Failed to load connections (HTTP ${res.status})`);
        return;
      }
      setItems((await res.json()) as ConnectionItem[]);
      setLoadError(null);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setLoadError("Failed to load connections");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void fetchConnections(controller.signal);
    return () => controller.abort();
  }, [fetchConnections]);

  async function disconnect(item: ConnectionItem) {
    setWorking(item.provider);
    try {
      const res = await apiFetch(`/api/auth/me/connections/${item.provider}`, {
        method: "DELETE",
        skipAuthRedirect: true,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toast.error(
          (data as { detail?: string }).detail ||
            `Failed to disconnect (HTTP ${res.status})`,
        );
        return;
      }
      toast.success(
        `Disconnected ${item.provider === "google" ? "Google" : item.provider}`,
      );
      setUnlinkConfirm(null);
      await fetchConnections();
    } catch {
      toast.error("Network error — please try again");
    } finally {
      setWorking(null);
    }
  }

  return (
    <SectionCard
      icon={<Link2 className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />}
      title="Connected accounts"
    >
      {loading ? (
        <div className="h-14 animate-pulse rounded-md bg-zinc-200/70 dark:bg-zinc-800/60" />
      ) : (
        <>
          {loadError && <InlineError>{loadError}</InlineError>}
          <ul className="divide-y divide-zinc-200 overflow-hidden rounded-lg border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
            {(items ?? []).map((item) => (
              <li
                key={item.provider}
                className="flex flex-col gap-2 px-3 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-zinc-100 dark:bg-zinc-800">
                    <Chrome className="h-4 w-4 text-zinc-600 dark:text-zinc-300" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-900 dark:text-white">
                      {item.provider === "google" ? "Google" : item.provider}
                    </p>
                    {item.linked ? (
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">
                        {item.email || "Linked"}
                        {item.linked_at &&
                          ` · linked ${formatRelativeTime(item.linked_at)}`}
                      </p>
                    ) : (
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">
                        Not connected.
                      </p>
                    )}
                  </div>
                </div>
                {item.linked ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={working === item.provider}
                    onClick={() => setUnlinkConfirm(item)}
                  >
                    Disconnect
                  </Button>
                ) : (
                  // TODO: wire client-side Google Identity Services to obtain
                  // an id_token and POST /api/auth/me/connections/google.
                  // Until then the simplest path is to instruct the user to
                  // sign in with Google from a fresh session.
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">
                    Sign out and sign in with Google to link.
                  </span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}

      <Dialog
        open={unlinkConfirm !== null}
        onOpenChange={(next) => {
          if (!next) setUnlinkConfirm(null);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Disconnect {unlinkConfirm?.provider ?? ""}?</DialogTitle>
            <DialogDescription>
              You&apos;ll need a password to sign in afterwards. If you don&apos;t
              have one set, the server will refuse to disconnect.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose
              render={<Button variant="outline" disabled={working !== null}>Cancel</Button>}
            />
            <Button
              type="button"
              variant="destructive"
              disabled={working !== null}
              onClick={() => unlinkConfirm && void disconnect(unlinkConfirm)}
            >
              {working !== null && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Disconnect
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </SectionCard>
  );
}

// ─── Default analysis options ──────────────────────────────────────────────

const ANALYSIS_TOGGLES: ReadonlyArray<{
  key: keyof AnalysisPreferences;
  label: string;
  help: string;
}> = [
  {
    key: "check_citations",
    label: "Check citations",
    help: "Verify cited URLs and DOIs are accessible and not retracted.",
  },
  {
    key: "trace_misinfo_origins",
    label: "Trace misinformation origins",
    help: "Try to find where flagged claims first appeared online.",
  },
  {
    key: "researcher_field_inference",
    label: "Researcher field inference",
    help: "Infer a researcher's field from their publications.",
  },
];

function AnalysisPreferencesSection() {
  const [prefs, setPrefs] = useState<AnalysisPreferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const res = await apiFetch("/api/auth/me/analysis-preferences", {
          signal: controller.signal,
        });
        if (!res.ok) {
          setLoadError(`Failed to load preferences (HTTP ${res.status})`);
          return;
        }
        setPrefs((await res.json()) as AnalysisPreferences);
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") return;
        setLoadError("Failed to load preferences");
      } finally {
        setLoading(false);
      }
    })();
    return () => controller.abort();
  }, []);

  async function persist(next: AnalysisPreferences) {
    setSaving(true);
    try {
      const res = await apiFetch("/api/auth/me/analysis-preferences", {
        method: "PUT",
        body: JSON.stringify(next),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        toast.error(
          (data as { detail?: string }).detail || "Failed to save preferences",
        );
        return;
      }
      toast.success("Analysis preferences saved");
    } catch {
      toast.error("Network error — please try again");
    } finally {
      setSaving(false);
    }
  }

  function toggle(key: keyof AnalysisPreferences) {
    if (!prefs) return;
    const next = { ...prefs, [key]: !prefs[key] };
    setPrefs(next);
    void persist(next);
  }

  return (
    <SectionCard
      icon={<Sliders className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />}
      title="Default analysis options"
      action={
        saving ? (
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
          {loadError && <InlineError>{loadError}</InlineError>}
          <div className="space-y-1">
            {ANALYSIS_TOGGLES.map((t) => {
              const value = prefs?.[t.key] ?? false;
              const inputId = `analysis-${t.key}`;
              return (
                <div
                  key={t.key}
                  className="flex items-start justify-between gap-4 rounded-lg px-3 py-2.5 hover:bg-zinc-50 dark:hover:bg-zinc-800/40"
                >
                  <div className="min-w-0 flex-1">
                    <Label
                      htmlFor={inputId}
                      className="cursor-pointer text-sm font-medium text-zinc-900 dark:text-white"
                    >
                      {t.label}
                    </Label>
                    <p className="mt-0.5 text-xs text-zinc-600 dark:text-zinc-400">
                      {t.help}
                    </p>
                  </div>
                  <ToggleSwitch
                    id={inputId}
                    checked={value}
                    onChange={() => toggle(t.key)}
                    ariaLabel={t.label}
                  />
                </div>
              );
            })}
          </div>
        </>
      )}
    </SectionCard>
  );
}

// ─── Shared bits ───────────────────────────────────────────────────────────

// ─── Scheduled Reports ─────────────────────────────────────────────────────

interface ReportSchedule {
  id: string;
  user_id: string;
  frequency: string;
  template: string;
  active: boolean;
  last_run_at: string | null;
  next_run_at: string;
  created_at: string;
}

const SCHEDULE_TEMPLATE_OPTIONS = [
  { value: "executive_summary", label: "Executive summary" },
  { value: "full", label: "Full detailed" },
] as const;

function ScheduledReportsSection() {
  const [schedules, setSchedules] = useState<ReportSchedule[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [frequency, setFrequency] = useState<"weekly" | "monthly">("weekly");
  const [template, setTemplate] = useState<string>("executive_summary");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch("/api/me/report-schedules/");
      if (!res.ok) throw new Error("load failed");
      const data = (await res.json()) as ReportSchedule[];
      setSchedules(data);
    } catch {
      setError("Could not load scheduled reports.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function createSchedule() {
    setError(null);
    setCreating(true);
    try {
      const res = await apiFetch("/api/me/report-schedules/", {
        method: "POST",
        body: JSON.stringify({ frequency, template }),
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(data.detail || "Failed to create schedule");
      }
      await refresh();
      toast.success("Schedule created");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to create schedule";
      setError(msg);
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  }

  async function toggleSchedule(s: ReportSchedule) {
    try {
      const res = await apiFetch(`/api/me/report-schedules/${s.id}`, {
        method: "PATCH",
        body: JSON.stringify({ active: !s.active }),
      });
      if (!res.ok) throw new Error("update failed");
      await refresh();
    } catch {
      toast.error("Could not update schedule");
    }
  }

  async function deleteSchedule(s: ReportSchedule) {
    if (!confirm(`Delete this ${s.frequency} schedule?`)) return;
    try {
      const res = await apiFetch(`/api/me/report-schedules/${s.id}`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) throw new Error("delete failed");
      await refresh();
      toast.success("Schedule deleted");
    } catch {
      toast.error("Could not delete schedule");
    }
  }

  return (
    <SectionCard
      icon={<CalendarClock className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />}
      title="Scheduled reports"
    >
      <p className="text-sm text-zinc-700 dark:text-zinc-300">
        Generate a recurring summary of your recent activity. Reports show up
        in your <Link href="/reports" className="text-brand underline-offset-2 hover:underline dark:text-brand-fg">Reports</Link> list automatically.
      </p>

      {error && <InlineError>{error}</InlineError>}

      <div className="grid grid-cols-1 gap-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-800/30 sm:grid-cols-3">
        <div className="space-y-1">
          <Label htmlFor="schedule-frequency" className="text-xs text-zinc-700 dark:text-zinc-300">
            Frequency
          </Label>
          <select
            id="schedule-frequency"
            value={frequency}
            onChange={(e) => setFrequency(e.target.value as "weekly" | "monthly")}
            className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          >
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="schedule-template" className="text-xs text-zinc-700 dark:text-zinc-300">
            Template
          </Label>
          <select
            id="schedule-template"
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
            className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          >
            {SCHEDULE_TEMPLATE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
        <div className="flex items-end">
          <Button
            onClick={createSchedule}
            disabled={creating}
            className="w-full bg-brand text-white hover:bg-brand-hover"
          >
            {creating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Create schedule
          </Button>
        </div>
      </div>

      {loading ? (
        <SkeletonField />
      ) : schedules && schedules.length > 0 ? (
        <ul className="space-y-2">
          {schedules.map((s) => (
            <li
              key={s.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900/40"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                  {s.frequency === "weekly" ? "Weekly" : "Monthly"} · {s.template === "full" ? "Full detailed" : "Executive summary"}
                </p>
                <p className="text-xs text-zinc-600 dark:text-zinc-400">
                  Next run: {new Date(s.next_run_at).toLocaleString()}
                  {s.last_run_at && ` · Last run: ${new Date(s.last_run_at).toLocaleDateString()}`}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <ToggleSwitch
                  id={`schedule-active-${s.id}`}
                  checked={s.active}
                  onChange={() => toggleSchedule(s)}
                  ariaLabel="Toggle schedule active"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10"
                  onClick={() => deleteSchedule(s)}
                  aria-label="Delete schedule"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          No scheduled reports yet.
        </p>
      )}
    </SectionCard>
  );
}

// ─── Billing (Phase D scaffolding) ─────────────────────────────────────────

const SUBSCRIPTION_STATE_LABEL: Record<ProfileResponse["subscription_state"], string> = {
  none: "No subscription",
  active: "Active",
  past_due: "Past due",
  cancelled: "Cancelled",
  paused: "Paused",
};

const SUBSCRIPTION_STATE_TINT: Record<ProfileResponse["subscription_state"], string> = {
  none: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  active: "bg-emerald-500/15 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300",
  past_due: "bg-amber-500/15 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300",
  cancelled: "bg-rose-500/15 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300",
  paused: "bg-sky-500/15 text-sky-700 dark:bg-sky-500/20 dark:text-sky-300",
};

/**
 * Billing settings shell. Renders the tier + subscription state badge
 * for everyone. "Manage subscription" is deliberately disabled — the
 * payment processor isn't wired yet (Phase D is scaffolding only).
 *
 * Once a processor lands, the disabled button becomes a real link to
 * the processor's customer portal and this component shows next /
 * last billing dates, invoice history, etc.
 */
function BillingSection({ profile }: { profile: ProfileResponse }) {
  // Wire active CTAs based on tier so the user always has a next step
  // instead of a disabled placeholder button. Free + pro → upgrade
  // path; team → contact sales (since team tier handles seats / org
  // billing differently).
  const isNoSubscription = profile.subscription_state === "none";
  const upgradeHref = profile.tier === "free" ? "/pricing#pro" : "/pricing#team";

  return (
    <SectionCard
      icon={<BarChart3 className="h-5 w-5 text-fg-secondary" />}
      title="Billing & subscription"
      description="Your current plan, next billing date, and account-level upgrade or change options."
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-fg-tertiary">
              Current plan
            </p>
            <p className="mt-1 font-display text-lg font-semibold capitalize text-fg-primary">
              {profile.tier}
            </p>
          </div>
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-medium ${SUBSCRIPTION_STATE_TINT[profile.subscription_state]}`}
          >
            {SUBSCRIPTION_STATE_LABEL[profile.subscription_state]}
          </span>
        </div>

        {profile.next_billing_date && (
          <p className="text-sm text-fg-secondary">
            Next billing date:{" "}
            <time dateTime={profile.next_billing_date}>
              {new Date(profile.next_billing_date).toLocaleDateString()}
            </time>
          </p>
        )}
        {profile.last_billing_date && !profile.next_billing_date && (
          <p className="text-sm text-fg-secondary">
            Last billed:{" "}
            <time dateTime={profile.last_billing_date}>
              {new Date(profile.last_billing_date).toLocaleDateString()}
            </time>
          </p>
        )}

        <div className="rounded-md border border-border-default bg-brand-soft/40 p-3 text-xs text-fg-secondary">
          {isNoSubscription ? (
            <>
              You&rsquo;re on the {profile.tier} plan. Self-serve checkout
              ships when our payment processor goes live — for now use the
              link below to start your upgrade.
            </>
          ) : (
            <>
              Self-serve billing portal lands when our payment processor
              goes live. Until then, contact{" "}
              <a
                href="mailto:info@example.invalid"
                className="text-brand-fg underline-offset-2 hover:underline"
              >
                info@example.invalid
              </a>{" "}
              for changes to your subscription.
            </>
          )}
        </div>

        {/* Tier-conditional CTA. Free/pro see "Upgrade to <next>"; team
            see "Contact sales" since their billing is org-managed. */}
        <div className="flex flex-wrap gap-2">
          {profile.tier !== "team" && (
            <Link
              href={upgradeHref}
              className="inline-flex h-9 items-center rounded-lg bg-brand px-4 text-sm font-medium text-white shadow-sm shadow-brand/20 transition-colors hover:bg-brand-hover"
            >
              {profile.tier === "free" ? "Upgrade to Pro" : "Upgrade to Team"}
            </Link>
          )}
          <Link
            href="/contact-sales"
            className="inline-flex h-9 items-center rounded-lg border border-border-default px-4 text-sm font-medium text-fg-primary transition-colors hover:bg-brand-soft"
          >
            {profile.tier === "team" ? "Contact sales" : "Talk to sales"}
          </Link>
        </div>
      </div>
    </SectionCard>
  );
}



// ─── Branding (white-label, team tier) ─────────────────────────────────────

interface OrgBranding {
  id: string;
  name: string;
  logo_url: string | null;
  primary_color: string | null;
  secondary_color: string | null;
}

function BrandingSection({ orgId }: { orgId: string }) {
  const [branding, setBranding] = useState<OrgBranding | null>(null);
  const [loading, setLoading] = useState(true);
  const [logoUrl, setLogoUrl] = useState("");
  const [primaryColor, setPrimaryColor] = useState("");
  const [secondaryColor, setSecondaryColor] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch(`/api/organizations/${orgId}/branding`);
        if (!res.ok) throw new Error("load failed");
        const data = (await res.json()) as OrgBranding;
        if (cancelled) return;
        setBranding(data);
        setLogoUrl(data.logo_url || "");
        setPrimaryColor(data.primary_color || "");
        setSecondaryColor(data.secondary_color || "");
      } catch {
        if (!cancelled) setError("Could not load branding settings.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  async function save() {
    setError(null);
    setSaving(true);
    try {
      const res = await apiFetch(`/api/organizations/${orgId}/branding`, {
        method: "PUT",
        body: JSON.stringify({
          logo_url: logoUrl || null,
          primary_color: primaryColor || null,
          secondary_color: secondaryColor || null,
        }),
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(data.detail || "Failed to save branding");
      }
      const updated = (await res.json()) as OrgBranding;
      setBranding(updated);
      toast.success("Branding updated");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to save";
      setError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <SectionCard
      icon={<Palette className="h-5 w-5 text-zinc-500 dark:text-zinc-400" />}
      title={branding ? `Branding · ${branding.name}` : "Branding"}
    >
      <p className="text-sm text-zinc-700 dark:text-zinc-300">
        Replace ArtiProof&apos;s logo and color in PDF reports your team
        generates. Leave blank to use the default.
      </p>
      {error && <InlineError>{error}</InlineError>}
      {loading ? (
        <SkeletonField />
      ) : (
        <>
          <div className="space-y-2">
            <Label htmlFor="branding-logo" className="text-zinc-700 dark:text-zinc-300">
              Logo URL
            </Label>
            <Input
              id="branding-logo"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              placeholder="https://example.com/logo.png"
              className="border-zinc-300 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
            />
            <p className="text-xs text-zinc-600 dark:text-zinc-400">
              PNG or SVG, max 200×40px renders best.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="branding-primary" className="text-zinc-700 dark:text-zinc-300">
                Primary color
              </Label>
              <div className="flex items-center gap-2">
                <Input
                  id="branding-primary"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  placeholder="#7C2828"
                  className="border-zinc-300 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
                />
                {primaryColor && (
                  <span
                    aria-hidden="true"
                    className="h-8 w-8 shrink-0 rounded border border-zinc-300 dark:border-zinc-700"
                    style={{ background: primaryColor }}
                  />
                )}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="branding-secondary" className="text-zinc-700 dark:text-zinc-300">
                Secondary color
              </Label>
              <div className="flex items-center gap-2">
                <Input
                  id="branding-secondary"
                  value={secondaryColor}
                  onChange={(e) => setSecondaryColor(e.target.value)}
                  placeholder="#C8901E"
                  className="border-zinc-300 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-white"
                />
                {secondaryColor && (
                  <span
                    aria-hidden="true"
                    className="h-8 w-8 shrink-0 rounded border border-zinc-300 dark:border-zinc-700"
                    style={{ background: secondaryColor }}
                  />
                )}
              </div>
            </div>
          </div>
          <Button
            onClick={save}
            disabled={saving}
            className="bg-brand text-white hover:bg-brand-hover"
          >
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Save branding
          </Button>
        </>
      )}
    </SectionCard>
  );
}

function SectionCard({
  icon,
  title,
  description,
  action,
  children,
}: {
  icon: ReactNode;
  title: string;
  /** Optional sub-heading under the title (renders muted). Use for
   *  brief context that explains WHAT the section controls. */
  description?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card className="border-border-default bg-surface-card">
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <CardTitle className="flex items-center gap-2 text-fg-primary">
              {icon}
              {title}
            </CardTitle>
            {description && (
              <p className="mt-1 text-xs text-fg-secondary">{description}</p>
            )}
          </div>
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
