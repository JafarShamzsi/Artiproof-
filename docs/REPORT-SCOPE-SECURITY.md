# Report scope security, SECURITY-02

Refs #25. Depends on SECURITY-01 #23. Device: axel-windows.
Implementation base: `b475587255e27aab730fdb9a4fa3c8529f6a3ba9`.
This is a bounded implementation, not release approval.

## Scope contract

- Interactive source/researcher, full/executive, comparison and institutional
  audit reports inherit the original inputs' `organization_id`, including NULL
  for personal work. Joining org B or moving from A to B does not transfer it.
- Every input is loaded with the existing soft-delete filter and authorized
  using the existing owner/org-admin policy. Direct ownership of prior-org
  work is preserved. Access does not authorize a tenant transfer.
- Comparison/audit inputs must all have the same scope. Personal plus org or
  org A plus org B returns 400 before narrative/PDF generation or persistence.
- A new-org admin cannot read/download these prior/personal reports merely
  because the author joined their organization. Prior-org admin access remains
  bound to the prior org, per the existing policy. Direct-owner access remains.
- Branding applies only when current organization and non-personal report
  scope agree. Regeneration does not relabel prior work with a new employer.

## Scheduling is deliberately unavailable

`ReportSchedule` has user ownership but no durable original tenant scope. Neither
its timestamps nor the user's mutable current org proves that scope. No schema
change, migration, backfill, or inference of historical scope is made here.

- Valid creation requests return **503** with an explicit disabled explanation.
  Invalid multi-record schedule templates retain their existing 400 validation.
- Reactivation returns **503** after the usual ownership check. Inspection,
  deletion and pausing remain available. A successful settings update disables
  the row. Historical rows may still display their stored active flag until
  paused/updated; that flag does **not** mean execution is enabled.
- Direct/manual sweep calls raise an explicit disabled error before any DB
  query, PDF generation, email delivery or run timestamp change.
- Beat registration removes only this sweep's entry. A previously queued task
  returns `status=disabled`, `generated=0`, `sent=0`, logs the reason and never
  opens a DB session. It cannot claim a summary was sent.
- All scheduled summaries are unavailable, including otherwise personal ones.
  Interactive same-scope reports remain available.

Safe re-enable requires a manager-approved durable scope/provenance model and
migration, explicit authorization for selecting inputs, execution-time owner and
membership revalidation, immutable original scope across org moves, scoped
history predicates, safe legacy disposition, honest delivery status, and real
PostgreSQL/worker tests. Ambiguous legacy rows must remain disabled; do not
automatically assign the current org. Resume must not sweep prior-org history.

## Reader inspection and bounded consequences

- `reports.py`: authenticated JSON, download, annotation and token-rotation
  routes authorize the persisted report, not the author's current org. Cached
  artifact reads occur only after report authorization or a valid share token.
- On cache miss, regeneration now requires every recorded input to remain
  present/non-deleted and in the persisted report scope. Drift or a partial
  comparison/audit returns **410**, including through a public share download.
  A same-scope cached PDF remains an existing snapshot; this is not a new
  revocation/retention model.
- Public share JSON/PDF routes remain bearer-token capabilities with existing
  expiry/deletion checks. This change does not revoke already-issued tokens or
  remove public sharing. Do not treat tenant isolation as share-link revocation.
- `auth.py` account export reads report metadata by `Report.user_id`; no new-org
  selector or derived-report re-stamping was found. Personal lists/search and
  dashboard counts remain owner-filtered. SECURITY-01's team activity/member
  usage queries filter the resource's org, so correct report scope is required.
- Artifact cleanup/storage does not grant access itself. No changes were made
  to export, auth, analytics, org, admin, ownership helpers, storage or frontend.

Existing incorrectly stamped reports/cached PDFs/shared links are **not repaired**.
Scheduled legacy summaries lack input provenance. Manager must approve a separate
historical inventory/quarantine or verify clean pilot data before release. No
production or customer-data inspection occurred. Global stale-session/admin-pointer
authorization work remains SECURITY-01's lane and dependency, not solved here.

## Verification history, 2026-11-06

Isolated interpreter `PY`:
`C:/Users/Axel/AppData/Local/Temp/opencode/security-02-venv/Scripts/python.exe`.
Created via the existing interpreter's `-m venv`; shared audit venv not modified.
Dependencies installed from backend requirements plus Ruff only in this isolated
environment. Commands below run from `backend`. No secrets or `.env` read, no
live-provider calls, service restart/reload or production access.

| Command | Actual result |
| --- | --- |
| Before production edits: `PY -m pytest -q tests/test_report_scope_security.py --tb=line --disable-warnings` | **17 failed, 4 passed**; all expected defects reproduced after correcting initial stub-only fixture errors |
| Recovery targeted run of that initial suite | **21 passed** |
| Final `PY -m pytest -q tests/test_report_scope_security.py --tb=short --disable-warnings` | **34 passed** |
| Final affected run: `PY -m pytest -q tests/test_report_scope_security.py tests/test_reports_auth.py tests/test_report_features.py tests/test_source_report_availability.py tests/test_researcher_report_evidence.py tests/test_report_assets.py --tb=short --disable-warnings` | **94 passed, 2 failed** |
| Final full backend: `PY -m pytest -q --tb=short --disable-warnings` | **630 passed, 2 failed, 52 deselected** |
| `PY -m pytest -q -m integration tests/test_report_scope_integration.py -rs --disable-warnings` | **13 skipped**, dedicated PostgreSQL URL absent; no database guarantees established |
| `PY -m ruff check --select E9,F63,F7,F82 app/routers/reports.py app/routers/report_schedules.py app/tasks/scheduled_reports.py tests/test_report_scope_security.py tests/test_report_scope_integration.py` | Passed |
| `PY -m ruff check tests/test_report_scope_security.py tests/test_report_scope_integration.py` | Passed |
| `PY -m pip check` | No broken requirements |
| `git diff --check` | Passed |

The initial two failures were in then-unowned `tests/test_report_features.py`:
`test_create_schedule_happy_path` expects 201, now correctly gets 503;
`test_run_due_schedules_with_non_empty_input` patches the removed task-local
`html_to_pdf` symbol and expects the now-disabled generation path. These are
behavior/test-contract conflicts introduced by required disablement, **not a
green full suite at that revision**. Manager subsequently authorized correction
of exactly those two tests in issue #25, comment 6688566389. They now require
explicit 503/disabled status, no history/owner query, no report/schedule writes,
no PDF/artifact work, no email and no successful-run timestamp advancement.
Unrelated tests are unchanged; no skips/xfails or weakened gates were added.

Bounded test-contract follow-up, same isolated interpreter/environment:

| Command | Actual result |
| --- | --- |
| `PY -m pytest -q tests/test_report_features.py tests/test_report_scope_security.py --tb=short --disable-warnings` | **65 passed** |
| `PY -m pytest -q tests/test_report_scope_security.py --tb=short --disable-warnings` | **34 passed** |
| `PY -m pytest -q --tb=short --disable-warnings` | **632 passed, 52 deselected**, supersedes the two prior failures |
| `PY -m pytest -q -m integration tests/test_report_scope_integration.py -rs --disable-warnings` | **13 skipped**, dedicated PostgreSQL URL still absent |
| `PY -m ruff check --select E9,F63,F7,F82 tests/test_report_features.py tests/test_report_scope_security.py tests/test_report_scope_integration.py` | Passed |

Stacked PR #27 targets SECURITY-01's branch, not main. Main-target-only workflow
triggers do not provide backend/PostgreSQL CI coverage for this stack. Combined
service-backed acceptance remains manager/CI-01 work, not an inferred green gate.
The initial broader Ruff run also reported existing FastAPI/style warnings;
only the error gate and full lint of the two new test files pass. Existing
runtime/deprecation warnings remain. No frontend build applies to this lane.

### Independent review corrections, successor to 9411a461

Manager's full PR #27 review comment 6688859111 requested changes. This revision:

- F1: fixture users now include required `full_name`, verified by a unit
  regression against the actual fixture factory. All three HTTP actors are
  persisted users with verified-email timestamps and persisted session rows.
- F2: no synthetic actors in the isolation acceptance cases. An isolated
  reports-only FastAPI app uses real bearer JWT decoding, session validation,
  `get_current_user`, membership-role lookup, quota and report routes. Only the
  DB dependency selects the dedicated test session factory; auth/ownership are
  not overridden. Existing session tokens are issued before a committed fixture
  membership/pointer transition from personal/org A to B. Both the new admin's
  denial and retained owner/prior-org-admin access are asserted for JSON and
  PDF downloads. Personal work also denies the prior-org admin. This is a real
  database fixture transition, **not** consent/signup/browser-flow acceptance.
- F2: private bearer and unauthenticated public-share cache-miss downloads cover
  all five input/template branches for unchanged scope (200), scope drift,
  missing references, soft deletion and real hard deletion (410). The hard-delete
  single-input cases explicitly check persisted FK SET NULL on a new connection.
  Denied regeneration performs no data/narrative/render/artifact work and does
  not replace the cached path. The original report scope stays fixed.
- F2: mixed personal/org and org-A/org-B generation asserts **before rollback**
  that branding, all data loaders, narratives, renderers, PDF conversion/artifact
  saving, `add`, `add_all`, `flush` and `commit` are not called. Unit tests check
  the same contract; PostgreSQL tests wrap the real session methods with spies.
- F3: recognized `source_verification`/`researcher_integrity` reports using full
  or executive templates with missing single-input FKs now return 410, covering
  ON DELETE SET NULL. Unknown/inputless report types retain 500; no general
  exception swallowing or conversion of every render failure into 410.

| Command | Actual successor result |
| --- | --- |
| Pre-fix `PY -m pytest -q tests/test_report_scope_security.py -k 'required_name or null_fk' --tb=short --disable-warnings` | **5 failed**, missing fixture name and four 500-versus-410 cases |
| `PY -m pytest -q tests/test_report_scope_security.py --tb=short --disable-warnings` | **40 passed** |
| Affected six-file suite listed above | **102 passed** |
| `PY -m pytest -q --tb=short --disable-warnings` | **638 passed, 104 deselected** |
| `PY -m pytest -q -m integration tests/test_report_scope_integration.py -rs --disable-warnings` | **65 skipped**, dedicated PostgreSQL URL absent; expanded from the prior 13 cases, **none service-verified locally** |
| `PY -m ruff check tests/test_report_scope_security.py tests/test_report_scope_integration.py` | Passed |
| `PY -m ruff check --select E9,F63,F7,F82 app/routers/reports.py app/routers/report_schedules.py app/tasks/scheduled_reports.py tests/test_report_features.py tests/test_report_scope_security.py tests/test_report_scope_integration.py` | Passed |
| `git diff --check` | Passed |

No new skip/xfail mechanism was introduced to obtain green. The existing opt-in
fixture's absent-service skip applies to the expanded matrix. CI02 owns combined
service-backed execution separately and must run this successor, not infer its
results from the earlier 13-case suite or the stack's main-only workflow trigger.
Independent exact-successor-SHA review remains required. No local service start,
reload, credential broadening, shared environment mutation or production access.

The PostgreSQL tests use an explicitly supplied, dedicated migrated
`ARTIPROOF_INTEGRATION_DATABASE_URL` (asyncpg only), UUID fixture rows and
fixture-owned cleanup, with independent sessions verifying persisted report
scope and admin denial, mixed-scope rejection/no report, and disabled schedules.
Rendering/narratives are stubbed to avoid filesystem/provider side effects;
DB persistence/queries/auth/membership/session lookups are real when enabled.
No SQLite fallback or customer
records. These tests are authored but **not executed against PostgreSQL here**.
Manager/CI-01 must add this file to the explicit PostgreSQL CI selection. No CI
edits were made. Exact commit SHA and remote state are recorded in the draft PR.

## Rollback and outstanding acceptance

Manager may withdraw/revert this commit; no schema rollback is needed. Reverting
restores the known scope-transfer/scheduling defect, so unsafe scheduling and
derived-report generation must remain disabled before any such release. Existing
data remediation, service-backed isolation, remote CI and
independent review of the exact head SHA remain gates. No merge or deployment
is authorized or performed.
