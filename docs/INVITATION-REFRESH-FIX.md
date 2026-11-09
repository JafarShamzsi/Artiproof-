# AUTH-02 invitation refresh continuity

**Current follow-up:** #45 adds account-identity isolation below. The #41
results and environment failures in the first sections are retained historical
evidence. Manager later permitted physical worktree-local Node dependencies;
both production builds now pass. Real authenticated acceptance remains blocked.

Agent-Tag: AUTH-02. Device-Tag: axel-windows. References #41, #34 and
test-harness dependency #43. Prepared base:
`66ac5e69bda2ff23f66aafda90b8ea9d4d06d84b` (main `bcd645b` plus unchanged
QA-01 harness head `b837cf498aba152d7f17278ef935aa9c38765836`).
The draft PR and exact-SHA handoff identify the final documentation-inclusive head.

## Cause and bounded correction

Installed NextAuth 4.24.13 `react/index.js:482-540` computes status from its
loading flag. `update()` sets loading before fetching CSRF/session, clears it
after the response, then updates session and returns the authoritative result.
The register page previously moved `InvitationConsent` between a standalone
branch and inside the signup form during authenticated → loading → authenticated.
React unmounted it, losing reviewed invitation, enrollment/retry and confirmation.

The standalone branch now also covers loading. The consent component displays
only a session-checking status during loading: no review, acceptance or team
navigation. Unauthenticated status still switches back to signup and unmounts
the previous authenticated consent. A changed invitation token still changes
the component key. No remembered authentication authorizes actions.

Explicit review/acceptance and authoritative `update({ refreshAccount: true })`
validation are unchanged. Success still requires a returned user, matching
organization and no account-refresh error. Enrollment recorded before a refresh
failure is retained so retry refreshes only the session, never repeats acceptance.
No sleeps, reloads, client-only organization checks or backend/auth changes.

## Regression evidence

Evidence prefix: `C:/Users/Axel/AppData/Local/hermes/cache/scratch/auth-02/`.

- Before application edits, the new parent + real consent regression ran with
  deferred refresh and explicit installed-library status transitions: **2 failed,
  3 passed**. Success confirmation disappeared and failure/retry disappeared,
  both resetting to Review invitation. Log: `regression-red.log`.
- After the correction, focused page/component suites: **17 passed**.
  Log: `regression-green.log`. Coverage includes refresh loading, failure/retry
  without another acceptance POST, token changes before/after acceptance, actual
  logout/auth loss (including late refresh completion), standard signup, initial
  loading, unverified/mismatched acceptance, authoritative refresh failures and
  the accepted `/team` link.
- Full frontend suite: **80 passed, 1 skipped** (existing BUILD-02 opt-in
  network-denied build test). TypeScript and full ESLint pass.

## Environment and acceptance

Before the manager safety stop, Docker reported engine 29.9.2 and the assigned
ports 3203/8203/55443/56443 were unused. This did **not** constrain Docker's
ambient context to a local engine; the inherited runner has that review finding.
Fresh npm/Python
dependencies and tools belong to AUTH-02 scratch; no other lane was modified.
QA-01 harness/specs remain byte-for-byte unchanged against the prepared base.
The unchanged runner creates fresh append-only UUID evidence directories under
QA-01 scratch, as authorized; existing QA evidence is not overwritten.

The first unchanged `run.py frontend-checks` evidence directory is
`scratch/qa-01/20261107-005231-5156402b`: unit/types/auth-file/full lint and
auth/default collection pass. **Production Turbopack build fails** because the
AUTH-02 scratch dependency junction points outside Turbopack's filesystem root.
This is an environment failure, not a passing build. Manager clarification was
requested before moving dependencies outside the scratch-only boundary.

The isolated webpack production build also fails on this cross-drive junction:
Next generates unresolved `./C:/.../next/dist/client/...` entry paths. Log:
`scratch/auth-02/build-webpack.log`. No dependency-placement exception was
granted and no config, dependency implementation or manifest was changed.

Pre-stop runs, retained as historical evidence, **not full acceptance**:

- `run.py all`, `scratch/qa-01/20261107-005331-68fa6247`: **exit 1**. Migrations
  completed; frontend readiness exited 1 at the same Turbopack junction error.
  No browser slice ran, so no new browser screenshot or journey pass exists.
  `checks.json` records both container cleanup commands exiting 0.
- `run.py api`, `scratch/qa-01/20261107-005433-0fa2a009`: logs record **3 passed**,
  with migrations and both container cleanup commands exiting 0. This completed
  during delivery of the manager safety steering, not after reauthorization.
  It does not establish browser acceptance or resolve runner safety findings.
- `run.py harness-checks`, `scratch/qa-01/20261107-005352-f9f9a26a`: the **six old
  safety/compile tests passed** and pip check passed. Those tests do not cover
  the newly discovered cleanup/context/egress gaps and are not a safety verdict.

The manager then prohibited all further Docker/server/browser/harness lifecycle:
independent review found cleanup can abort later cleanup/evidence on timeout,
Docker context is unconstrained, and browser egress observation is not
pre-dispatch prevention. AUTH-02 stopped lifecycle execution immediately and
made no harness edits. Manager separately reported verification using the
explicit local pipe: no QA containers and all four ports free. This is the
manager's cleanup observation, not a new AUTH-02 lifecycle verification.

**Real authenticated acceptance remains BLOCKED** pending QA-01 harness
correction, independent safety review, manager integration and an authorized
unchanged journey rerun. Do not infer it from component tests or hosted CI.

## Review, limitations and rollback

Independent QA-harness safety findings remain manager-owned and must be
integrated before acceptance. No harness correction is included here.
Exact-head independent review and manager combined CI remain required.

OAuth/Google-only/linked-provider, 2FA/TOTP/backup codes, external email delivery,
completed worker/provider analysis, styled WeasyPrint PDF and production/customer
acceptance remain unverified. Pending submissions/unassessed PDFs are not
completed analysis, and pending persistence alone does not establish broker
publication. Team controls/removal all-UI and former-owner policy gates
from QA-01 remain explicit; this fix does not broaden those claims.

Rollback: manager can revert the bounded frontend correction and associated
regressions; no schema/data migration or production action is involved. No
merge, deployment, provider call, real OAuth account, credential/dotenv read,
shared dependency mutation or global reload is authorized or performed.

## Issue #45: authenticated account replacement (separate follow-up)

Manager renewed AUTH-02's same-five-file claim for 45 minutes from reviewed
head `71f59437fcbadb74ed6291cc1caeb0e057327f4c`. Independent review accepted the
bounded #41 fix and separately reproduced an inherited A-to-B authenticated
replacement retaining A's confirmation. This is UI state isolation, not a new
backend authorization bypass or a production incident. The successor commit and
exact final SHA are identified in draft PR #44 and its handoff; the previously
reviewed commit is preserved.

### Installed-client trace and regression

NextAuth `SessionProvider` exposes its existing `data: session` during update
loading (`react/index.js:482-540`). Storage events call `_getSession` and replace
session directly without an intervening unauthenticated render (`383-448`).
The prior key used only the invitation token, so A's reviewed/accepted/enrolled
state could survive B's authenticated replacement. Identity is the existing
server-held `session.user.id`, populated by `lib/auth.ts:211-221`, not email or
organization metadata.

The rewritten page suite explicitly unmocks the shared setup's NextAuth stub.
It uses installed `SessionProvider`, `useSession`, real page/consent/apiFetch,
mocked fetch responses and actual storage event dispatch. No session hook/update
mock, backend, server, browser or external request is used. A session probe
observes loading with A's data still present. This is **jsdom client integration**,
not real authenticated HTTP/browser acceptance.

Before application edits: **7 failed / 5 passed**, demonstrating stale reviewed,
accepted and retry state, delayed completions and missing identity. Evidence:
`scratch/auth-02/identity-red-confirmed.log`. Initial fixture diagnostics remain
in `identity-red.log` and `identity-red-sessionprovider.log`; the first still
used the global setup stub and is not the intended reproduction.

### Bounded correction

- Parent keys consent by `[invitation token, session.user.id]`. Same-account
  loading and enrollment organization changes preserve the instance; account,
  token or missing-identity transitions reset it. Logout still discards state.
- Consent requires an account ID before actions/navigation. The refreshed session
  must match both the original account ID and invitation organization, with no
  refresh error. Missing identity requests sign-in again.
- An instance cleanup guard ignores obsolete success/error/finally completions.
  A delayed acceptance from A does not initiate session refresh after A's
  passive cleanup. Independent review later found the commit-to-passive gap in
  this initial guard; the correction and new evidence are recorded below.
  No implicit acceptance or enrollment replay is added.
- If NextAuth update was **already in flight**, the library itself can apply
  its eventual session response even after a storage replacement. A regression
  covers both a B response and an old A response: neither resurrects accepted
  consent. This local fix does **not** cancel NextAuth's internal request or
  establish global cross-tab/session/backend race correctness.

### Verification and dependency placement

Manager permitted ignored physical `frontend/node_modules`. Before removal,
the old entry was verified as a junction targeting only
`scratch/auth-02/npm/node_modules`. Nonrecursive `Directory.Delete` removed
the junction entry, not its target. Scratch dependencies/evidence remain.
Lockfile-preserving `npm --prefix frontend ci --no-audit --no-fund` installed
lane-local dependencies; no manifest/lockfile/config/global/shared change.
Installed npm reports three blocked dependency install scripts; all executed
checks below work with the installed packages.

- Focused page/component suites: **30 passed** (18 installed-client + 12 unit).
- Full frontend suite: **93 passed, 1 existing opt-in build skipped**.
- TypeScript `--noEmit`, full ESLint and diff checks pass.
- Supported webpack production build: **exit 0**, all 27 static pages generated.
  First attempt exceeded the outer tool's 120-second timeout during build traces;
  no matching owned build process remained, then a longer bounded rerun passed.
- Default Turbopack production build, separately: **exit 0**, 27 static pages.
- Builds used a non-secret allowlisted environment, synthetic build-only auth
  settings and metadata-only dotenv refusal. No application service was started.
- QA harness/spec and other restricted source blobs remain unchanged against
  the prepared base. No corrected QA branch was integrated by this worker.

Evidence under `scratch/auth-02/`: `identity-green.log`, `identity-unit-full.log`,
`identity-types.log`, `identity-lint.log`, `identity-build-webpack.log` (timeout),
`identity-build-webpack-retry.log` (pass), `identity-build-turbopack.log` (pass).
Final exact-head hosted checks are recorded separately in PR #44's handoff.

### Remaining gates

No Docker/container/server/browser/harness lifecycle ran in this renewed claim.
QA-01 correction, independent safety review, manager integration and explicit
authorization are still prerequisites for real unchanged journey acceptance.
The successor app SHA also requires new independent review; predecessor review
does not approve new code. All provider/OAuth/2FA/worker/PDF-style/customer gates
above remain unverified. Rollback can omit/revert only this successor commit,
preserving the independently accepted #41 fix. No merge or deploy is authorized.

## Issue #45 review correction: invalidate at commit, not passive cleanup

Manager/user renewed the same bounded five-file claim from
`c3bdba64bb845cef09a4e1e166fe0f0b1e07cfbf` after PR #44 review comment
`6697008525` requested changes. Claim/authorization is comment `6710509217`.
The earlier independent repeat/control batch stopped at an approval gate and
did not execute; it is not evidence. All checks here are fresh authorized local
mocked/jsdom/static/build executions using existing dependencies.

### Actual failing regression

The previous tests awaited `act` before resolving old A's result, inadvertently
flushing passive cleanup. A new commit probe instead resolves A's acceptance
from B's layout effect using installed React 19.2.4, installed NextAuth
SessionProvider and the actual page/consent/apiFetch with mocked HTTP. The
storage-triggered replacement is allowed through React's real scheduler outside
`act`; the temporary act-environment warning flag is restored in `finally`.
No hooks, lifecycle timing or authorization endpoints are replaced.

Before application edits, both normal and StrictMode tests **failed** with:

```text
B layout: release A acceptance
GET /api/auth/csrf
POST /api/auth/session
B passive
```

This proves a **new** update request could start after B committed, not merely
that an already-dispatched refresh could finish late. Exact red log:
`scratch/auth-02/commit-race-red.log` (**2 failed**, 18 tests filtered out by the
focused test-name selection). A second pre-fix run adding preview controls and
runtime identity inputs recorded **6 failed / 5 passed**, 20 filtered out:
`commit-race-and-id-red.log`. Truthy number/boolean/object/array IDs incorrectly
exposed Review invitation; null/undefined/empty string already failed closed.

### Minimal correction and preserved behavior

Consent starts inactive, is activated by layout-effect setup, and invalidated
by **layout cleanup during the replacement commit**. Entry guards and existing
post-await guards refuse obsolete work. StrictMode's cleanup/setup replay
reactivates the current instance, rather than leaving it permanently disabled.
The account/token key and authoritative returned-account/org/error validation
remain unchanged, so same-A loading, enrollment metadata changes and refresh-only
retry retain state. No acceptance replay or arbitrary app sleep/reload is added.

Both parent key construction and component authorization now accept only an
existing nonempty string account ID. Invalid runtime types normalize to missing
identity; there is no UUID/email/format restriction or identity invention.

### Fresh verification

- Focused page/component: **43 passed** (31 installed-client cases and 12 unit
  contracts), `commit-race-green.log`.
- Full frontend: **106 passed / 1 existing opt-in build skipped**,
  `commit-race-unit-full.log`.
- `tsc --noEmit` and full ESLint: **pass**, `commit-race-types.log` and
  `commit-race-lint.log`; diff checks pass.
- Supported webpack production build: **exit 0**, all 27 static pages generated,
  `commit-race-build-webpack.log`. Same allowlisted synthetic build environment
  and metadata-only dotenv refusal; no service startup. Default Turbopack was
  not rerun for this correction; its prior success above is predecessor evidence.
- New normal/StrictMode commit-window cases cover both delayed preview and
  acceptance. Same-account loading/failure/retry/org-change tests also run in
  StrictMode; direct replacement, missing identity, logout/token reset and the
  already-in-flight refresh cases remain passing.

Logs are under `C:/Users/Axel/AppData/Local/hermes/cache/scratch/auth-02/`.
Exact successor SHA, unchanged inherited harness blobs and bounded hosted CI
observation are published in PR #44 and issue #45 handoff. Only four of the five
owned files need changes in this correction; the unit contract file is unchanged.

### Limits / stop

This blocks new refresh work from an obsolete acceptance continuation after
replacement commit. It does **not** undo committed enrollment, cancel an already
dispatched backend request, or prevent NextAuth itself applying an already-in-flight
refresh response. No backend bypass or broad cross-tab/account race clearance is
claimed. All original provider/OAuth/2FA/worker/PDF/customer acceptance gaps remain.

No QA/harness, backend/auth.ts/types, config/manifests/CI or other-worktree edits;
no installs, Docker, browser/server/services, native probes, secrets/dotenv reads,
production/customer/provider access, merge/deploy or self-approval. Real journey
acceptance remains a separate manager-owned authorized integration gate. The new
exact app head requires independent review; the writer stops after handoff.
