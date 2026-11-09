# GDPR account deletion — operational runbook

Authoritative description of how ArtiProof honours **GDPR Article 17
(right to erasure)**. Every step below cites the file and line that
implements it so on-call can trace what happened to a specific
account.

For data portability (Article 20) see
[gdpr-export.md](./gdpr-export.md).

## Quick reference

| Step | Trigger | Latency | Reversible? |
|---|---|---|---|
| 1. Soft delete | User: Settings → Danger zone → Delete account | Immediate | Yes (admin restore) within 30 days |
| 2. Cascade soft delete | Same request | Immediate | Yes, restoring the user via admin doesn't auto-restore owned rows |
| 3. Login refused | Next request after soft delete | Immediate | n/a (login forbidden until restored) |
| 4. Hard delete | Daily Celery cleanup task | Within 30 days + 1 day | **No** |

## Step 1 — User-initiated soft delete

Endpoint: `DELETE /api/auth/me`
Implementation: `backend/app/routers/auth.py:747` (`delete_account`).

Requirements before the row is touched:

- Body field `confirm` must equal the literal string `"DELETE"`. The
  UI passes this verbatim from a confirmation dialog. Mistypes 400.
- `current_password` must verify against the stored bcrypt hash.
  Google-only accounts (no password set) fall through to the same
  401 — they need to set a password first via OAuth re-linking, then
  retry. (This is acknowledged as a UX rough edge; see the dialog
  copy in `frontend/src/app/(dashboard)/settings/page.tsx`.)

Effect:

- `User.deleted_at` set to `now` (UTC).
- `SourceCheck`, `ResearcherProfile`, `Report` rows owned by the user
  are also stamped with the same `deleted_at` so the cleanup task
  sweeps them together (`auth.py:773-800`).
- The next request bearing this user's JWT returns 401:
  `get_current_user` checks `user.deleted_at is not None` and rejects
  (`backend/app/utils/auth.py`). No "session sticking around" after
  the soft delete.

What is **not** touched at this stage:

- Active `Session` rows. Login is blocked by the dep check above, so
  there's no need to revoke individually; deletion happens at hard
  delete time.
- Uploaded files (PDFs in `backend/uploads/`). The orphan-file
  cleanup (`tasks/cleanup.py:107-150`) only removes files after both
  (a) no row references them AND (b) they're past
  `ORPHAN_FILE_GRACE_HOURS`. Until the user's rows hard-delete, the
  files are still referenced and stay on disk.

## Step 2 — Grace window (30 days)

The grace window is `SOFT_DELETE_GRACE_DAYS = 30`
(`backend/app/tasks/cleanup.py:35`).

During this window:

- The user **cannot log in**. The account is invisible to them.
- An **admin can restore** the account via
  `PATCH /api/admin/users/{id}` with body `{"restore": true}`
  (`backend/app/routers/admin.py:222`). The admin endpoint clears
  `User.deleted_at` and sets it back to `null`.
- **Restoring the user does NOT auto-restore owned source checks,
  researcher profiles, or reports** (they have their own
  `deleted_at` timestamps). This is intentional: in practice a user
  reactivating after a regret usually wants their dashboard back, so
  on-call should also run an UPDATE to clear `deleted_at` on the
  child rows if the restore is meant to be a full reversal. There is
  not (yet) a one-shot admin endpoint for this — track in Phase C.

Operational notes for on-call:

- **Restore window:** A restore at day 29 succeeds. A restore at day
  31 fails (the row is gone). There's no last-warning email yet
  (Phase B follow-up).
- **Restore audit:** Every admin PATCH writes an
  `AdminActorLog` row (see `admin.py`). When you restore, leave a
  brief reason in the audit note so the trail is legible.
- **Bulk restore not supported.** If a customer reports
  multiple-account regret, escalate to engineering — a one-off
  script is cheaper than building bulk endpoints for a rare case.

## Step 3 — Hard delete

Trigger: daily Celery beat task `hard_delete_expired_soft_deletes`
(`backend/app/tasks/cleanup.py:45`). Runs at 03:00 UTC per the beat
schedule.

What it does:

- Selects all rows where `deleted_at < (now - 30 days)`.
- Hard-deletes them. The database cascade does the rest:
  `User → Session` (CASCADE), `User → SourceCheck → ClaimAnalysis`
  + `AIDetectionResult` + `CitationCheck` (CASCADE),
  `User → ResearcherProfile → PublicationAnalysis` (CASCADE),
  `User → Report` (CASCADE).
- Files are removed by the orphan-file pass that runs in the same
  task immediately after — once the rows are gone, their referenced
  paths drop out of the "still referenced" set and the files become
  eligible for unlink (`cleanup.py:72`).

After this point the data is **unrecoverable from production**.
Postgres point-in-time recovery (Neon) could resurrect the rows from a
snapshot within the snapshot retention window, but that's a destructive
action and gated by Neon's policy + engineering approval.

## What support agents should know

- **"I deleted my account by mistake."** If less than 30 days have
  passed, restore via `PATCH /api/admin/users/{id} {"restore": true}`.
  Ask the user before doing it — they may have a security reason
  for the deletion.
- **"I want my data deleted right now, not in 30 days."** Tell them
  the 30-day grace is the regret window; the data is **invisible to
  every read path** during that period (no other user can see it,
  no aggregate queries surface it). For immediate hard delete, engineering
  can run a one-off SQL script — escalate.
- **"Did you really delete my data?"** The user can verify by trying
  to log in (401 on the soft-delete day; 401 with a different code
  after 30 days — the row no longer exists). For audit, the GDPR
  request can include a final confirmation email after the hard
  delete. **TODO:** wire this email; tracked in Phase C.

## Implementation cross-reference

| Concept | File:line |
|---|---|
| Soft-delete endpoint | `backend/app/routers/auth.py:747` |
| Cascade to owned rows | `backend/app/routers/auth.py:773-800` |
| 30-day constant | `backend/app/tasks/cleanup.py:35` |
| Hard-delete task | `backend/app/tasks/cleanup.py:45-68` |
| Orphan file sweep | `backend/app/tasks/cleanup.py:107-150` |
| Admin restore endpoint | `backend/app/routers/admin.py:222` |
| Auth dep rejects deleted | `backend/app/utils/auth.py` (`get_current_user`) |
| Soft-delete column mixin | `backend/app/models/mixins.py` (`SoftDeleteMixin`) |

## Audit checklist (annual)

Run before each compliance review:

- [ ] Confirm `SOFT_DELETE_GRACE_DAYS = 30` hasn't drifted.
- [ ] Confirm the beat schedule still includes
      `hard_delete_expired_soft_deletes` and that it ran successfully
      in the last 24h.
- [ ] Confirm no `deleted_at < now() - 31 days` rows remain in the
      DB (one-off SQL query).
- [ ] Confirm orphan-file pass cleared all unreferenced files in
      `backend/uploads/` older than the grace window.
- [ ] Diff this runbook against the actual file:line targets above;
      if they've drifted, update the table.

## Changelog

- 2026-05-29 — initial runbook; cross-references admin restore and
  the deep-health probe.
