# Team consent rollout: blocked pending evidence

SECURITY-01 / axel-windows, issue #19, draft PR #23. This is a rollout
checklist, **not** permission to deploy or evidence of historical cleanup.
The independent review of `b475587255e27aab730fdb9a4fa3c8529f6a3ba9`
was BLOCKED. Corrections require a new exact-SHA independent review and
service-backed checks before manager integration.
The subsequent `49184e3bee4a6e36c3342000df5acce080eb0938` review also
remained BLOCKED on the implicit audit-FK lock cycle described below.

## Existing data is not certified by the new guards

Legacy invitation issuance forcibly attached some existing accounts without
recipient acceptance. A membership row, user pointer, `joined_at`, or an old
`member_added` audit is not proof of consent. Migration 0013 also backfilled
membership/roles; that is structural data, not consent evidence.

Migration `0012_org_id_owned` propagated the owner's current organization onto
pre-existing source checks, researcher profiles and reports. Its SQL only checks
for a non-null user organization pointer, **not team tier or consent**, despite
the migration's introductory tier description. New resource-org predicates do
not distinguish these backfilled rows from legitimately organization-owned work.
The fixes do not retroactively isolate incorrectly scoped historical data.

Before any pilot using existing data, the manager must commission an authorized,
separately scoped audit and remediation plan:

1. Inventory enrollments without recipient acceptance evidence, pointer/member
   mismatches, multiple memberships, and resources affected by historical scope
   backfills or derived report/schedule scope transfers. Do not expose private
   titles/content while producing an inventory.
2. Quarantine uncertain enrollments/resources from team visibility using a
   separately reviewed mechanism. Do not infer ownership from current pointer,
   tier, timestamps, migration history alone, or a recreated membership.
3. Collect verified recipient re-consent for enrollment. Enrollment re-consent
   alone does not authorize publication of personal historical resources;
   historical resource ownership needs separate, attributable authorization.
4. Preserve original ownership/consent evidence and audit history. Any repair
   needs a reviewed dry-run, backups, bounded changes and rollback verification.
   Do not silently rewrite scopes or mark old invitations accepted.
5. Record exact evidence and independent approval before lifting quarantine.

Alternatively, the manager may authorize **verified clean pilot initialization**:
an isolated, fresh, migrated pilot database with no imported users, memberships,
resources, schedules or reports, documented provenance and no customer records.
“Development data probably looks clean” is not verification. Do not delete,
truncate, backfill or inspect production/customer data under this assignment.
Neither remediation nor clean initialization was performed by SECURITY-01.

## Runtime behavior and limits

- Generic platform-admin PATCH cannot reassign or clear an organization pointer.
  Invitations/recipient acceptance and membership-removal routes own enrollment.
- Source/researcher creation locks the user then organization and validates fresh
  membership. Pointer-only/mismatched/inactive enrollment fails closed; there is
  no automatic personal fallback or historical scope repair. A scope change
  while waiting fails the request instead of silently assigning a different one.
  Source bulk reacquires enrollment locks for every independently committed item.
- Invite/resend/revoke/role/remove reauthorize the actor after the organization
  lock using refreshed state. Lock order is user (if needed) -> organization ->
  invitation, with no actor-user lock taken after the organization lock.
  User/organization parent locks use **FOR NO KEY UPDATE**, not FOR UPDATE or
  the shared FOR KEY SHARE mode. Invitation row locks remain FOR UPDATE.
- Acceptance requires authenticated matching **verified email**, persistent token,
  current invitation state, competing-membership and seat checks. Viewing a URL
  or registering is not consent. Replay never re-enrolls a removed user.
- After acceptance, NextAuth update fetches `/api/auth/me` using its existing
  server-held bearer. Client organization/tier/role/token fields are ignored.
  Refresh failures preserve prior authorization and return a typed failure marker
  rather than throwing out the NextAuth session cookie. The UI must not display
  success or offer team navigation until synchronization succeeds. Enrollment
  may already be committed; retry only session refresh in that state.
- Tier/billing policy is not changed. New signup, sign-in and verification may
  require reopening the invitation. No new OAuth policy is introduced.
- SECURITY-02 exclusively owns derived interactive/scheduled-report scope fixes.
  SECURITY-01 does not certify these paths or edit report/schedule modules.

### Parent-row lock modes and implicit foreign-key locks

Explicit order alone was insufficient: transaction A could lock user U FOR
UPDATE and wait for organization O, while transaction B held O and tried to
insert an audit (or invitation) referencing U. PostgreSQL's FK check needs
FOR KEY SHARE on U, which conflicts with A's FOR UPDATE. Neither can commit.
This was a source-derived P1, not a locally reproduced PostgreSQL deadlock.

PostgreSQL 16 [13.3.2/Table 13.3](https://www.postgresql.org/docs/16/explicit-locking.html#LOCKING-ROWS)
shows that **NO KEY UPDATE conflicts with itself and UPDATE**, preserving
enrollment/seat writer exclusion, but is compatible with **KEY SHARE**. The
server's [RI FK check](https://github.com/postgres/postgres/blob/REL_16_STABLE/src/backend/utils/adt/ri_triggers.c)
constructs `SELECT 1 ... FOR KEY SHARE OF x` on the referenced parent.
Both `lock_user` and `lock_org` therefore use NO KEY UPDATE consistently.
Audits and constraints remain intact; this is not a skipped-audit workaround.

The installed SQLAlchemy API is counterintuitive: `with_for_update(key_share=True)`
**without** `read=True` compiles to `FOR NO KEY UPDATE` for PostgreSQL;
adding `read=True` would instead produce `FOR KEY SHARE` and lose writer
exclusion. The actual helper queries are compiled with `postgresql.dialect()`
in `tests/test_team_lock_modes.py`, including `populate_existing=True` checks.
Generic `str(query)` output or a hand-written stand-in query is not evidence
of the PostgreSQL lock clause. See the SQLAlchemy
[API documentation](https://docs.sqlalchemy.org/en/20/core/selectable.html#sqlalchemy.sql.expression.GenerativeSelect.with_for_update).

These enrollment/creation paths change non-key fields (e.g. organization
pointer, role, seat limit), not referenced user/org keys or unique identifiers.
Key-changing updates/deletions need stronger PostgreSQL locks; any future path
that changes such keys must be reviewed for upgrades/order and FK interactions.
No lock mode permits stale authorization: post-lock fresh membership/account
checks and user -> organization -> invitation ordering are unchanged.

The successor adds deterministic real-HTTP role/invite/remove vs source/researcher
creation races. Each holds the mutation's org lock after actual authorization,
observes the creation transaction waiting via `pg_blocking_pids`, then permits
the real mutation/FK/audit commit. Both requests must finish once, with one
resource/run/queued event and exactly one corresponding org audit. Separate
parent-lock cases require a real FK insert to commit while the parent lock is
held, then prove another serialization writer blocks until release. No automatic
retry counts as a pass. Cancellation and database statement/lock/idle budgets
bound fixture teardown; failed races must fail rather than hang cleanup.

CI-02's failure handoff on combined `fdd8c8e4116564e80257f089a14423bdc893bbfa`,
run `42246022046`, reported 41 passing consent tests and two failing invite
races. Both posted `new@integration.invalid`, rejected with 422 by EmailStr
before the expected lock. The shared race payload now uses a valid synthetic
`example.com` address; delivery stays mocked. A default-suite schema regression
also verifies that the old reserved-domain address remains rejected. Production
validation is not weakened. This hosted handoff is not this worker's DB rerun.

## Required verification before release

Use only an explicitly authorized disposable database migrated to the combined
branch's head. No SQLite substitution; never derive credentials from `.env` or
point tests at a customer database. The PostgreSQL fixture creates UUID-owned
rows and removes only its fixtures; it must not run alongside live workers that
could execute its synthetic queued analysis intents.

From `backend`, with isolated test dependencies and
`ARTIPROOF_INTEGRATION_DATABASE_URL=postgresql+asyncpg://...` set by the operator:

```text
python -m pytest -q
python -m pytest -q -m integration tests/test_team_consent_integration.py
python -m ruff check --select E9,F63,F7,F82 app
```

The integration suite includes actual bearer-authenticated HTTP dependencies,
acceptance -> account refresh -> team access with the same bearer, creation
denial/allowance and post-lock actor demotion/removal races. Races must observe
PostgreSQL blocking relationships with bounded waits, not infer synchronization
from sleeps. A skipped case is **not** verification. CI-02 owns the combined
real-service branch; manager must deliver the successor there for a zero-skips
rerun. This lane does not edit workflows or alter shared services/dependencies.
The correction run has no configured dedicated PostgreSQL URL; DB acceptance
remains unverified. Unit stubs and callback/component tests are not DB/browser
evidence.

From `frontend`, run unit tests, TypeScript, changed-file ESLint and the production
build. BUILD-01 owns the existing `/team` Suspense build correction. Do not copy
or modify team files to bypass that dependency. A compiled bundle followed by
prerender failure is not a successful production build.

Still required, with fresh consenting synthetic accounts and isolated services:

- Real browser signup -> email verification -> explicit invitation acceptance
  -> authoritative session refresh -> same-session team access; failed refresh
  must preserve prior authorization and not show success.
- Google-only account enrollment and mailbox verification. Google login's
  provider-verified email does not by itself establish the application's
  `email_verified_at` journey. Keep verified-email acceptance requirements;
  do not invent OAuth trust exceptions or claim unit mocks certify this path.
- Full existing/new-user 2FA challenge, verification, invitation and refresh
  journey. Mocked callbacks do not certify challenge handling or session cookies.
- SECURITY-02 report/schedule isolation, legacy-data remediation/clean pilot
  evidence, exact-SHA independent review and green combined-branch remote gates.

## Rollback and ownership

No migration, historical mutation, provider certification or production action
is part of this correction. Manager owns rollout and integration. Reverting the
code restores known enrollment/visibility defects; disable unsafe enrollment and
team-visibility surfaces before any separately authorized rollback. Never merge,
deploy, approve this work, or close #19 based only on the unit-test results.
