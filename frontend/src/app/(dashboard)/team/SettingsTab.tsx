"use client";

import { useState } from "react";
import { Loader2, Save } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { toast } from "@/lib/toast";
import type { OrgDetail } from "./types";

/**
 * Settings tab — admin-editable org fields.
 *
 * Mutable: name + contact_email. Seat limit is intentionally read-only
 * here — upgrading the cap goes through the billing flow (today:
 * contact-sales).
 *
 * The form is uncontrolled in the sense that it doesn't validate
 * client-side beyond `required`; the backend's Pydantic schema is the
 * source of truth and returns a 400 with `detail` on bad input.
 */
export function SettingsTab({
  org,
  onMutate,
}: {
  org: OrgDetail;
  onMutate: () => void;
}) {
  const [name, setName] = useState(org.name);
  const [contactEmail, setContactEmail] = useState(org.contact_email ?? "");
  const [saving, setSaving] = useState(false);

  const dirty = name !== org.name || contactEmail !== (org.contact_email ?? "");

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!dirty || saving) return;
    setSaving(true);
    try {
      const body: Record<string, string | null> = {};
      if (name !== org.name) body.name = name.trim();
      if (contactEmail !== (org.contact_email ?? "")) {
        body.contact_email = contactEmail.trim() || null;
      }
      const res = await apiFetch(`/api/organizations/${org.id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => ({}))) as { detail?: string };
        toast.error(data.detail || "Save failed");
        return;
      }
      toast.success("Team settings saved");
      onMutate();
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={save}
      className="space-y-6 rounded-lg border border-border-default bg-surface-card p-5"
    >
      <div>
        <label
          htmlFor="org-name"
          className="text-sm font-medium text-fg-primary"
        >
          Team name
        </label>
        <p className="mt-1 text-xs text-fg-secondary">
          What members see in their workspace header and in shared reports.
        </p>
        <input
          id="org-name"
          type="text"
          required
          minLength={2}
          maxLength={80}
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="mt-2 block w-full rounded-md border border-border-default bg-surface-base px-3 py-2 text-sm text-fg-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
        />
      </div>

      <div>
        <label
          htmlFor="org-contact-email"
          className="text-sm font-medium text-fg-primary"
        >
          Billing & admin contact email
        </label>
        <p className="mt-1 text-xs text-fg-secondary">
          Where renewal reminders and seat-cap warnings are sent. Defaults to
          the team owner&apos;s email.
        </p>
        <input
          id="org-contact-email"
          type="email"
          value={contactEmail}
          onChange={(e) => setContactEmail(e.target.value)}
          className="mt-2 block w-full rounded-md border border-border-default bg-surface-base px-3 py-2 text-sm text-fg-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
        />
      </div>

      <div className="rounded-md border border-border-default bg-surface-base p-3">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-fg-primary">Seat limit</p>
            <p className="text-xs text-fg-secondary">
              Your plan includes {org.seat_limit} seat
              {org.seat_limit === 1 ? "" : "s"} · {org.seat_used} in use.
            </p>
          </div>
          <a
            href="/contact-sales?plan=team-upgrade"
            className="inline-flex items-center rounded-md border border-border-default px-3 py-1.5 text-xs font-medium text-fg-primary hover:bg-brand-soft"
          >
            Request more seats
          </a>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={!dirty || saving}
          className="inline-flex h-9 items-center gap-1.5 rounded-md bg-brand px-4 text-sm font-medium text-white shadow-sm shadow-brand/30 hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Save changes
        </button>
      </div>
    </form>
  );
}
