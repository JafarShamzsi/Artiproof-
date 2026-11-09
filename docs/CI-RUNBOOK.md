# CI release gates

CI-01 / issue #18. Scope is workflows, Playwright configuration and the
manager-authorized queue dependency constraints/regressions, not application
behavior fixes or deployment. Required check names remain **backend** and
**frontend**; do not rename them or bypass a failing gate during integration.

## Execution contract

- CI, Security and CodeQL accept PRs to `main`, pushes to `main`,
  `workflow_dispatch` and merge-queue `merge_group: checks_requested`.
  Security/CodeQL also run weekly. Manual dispatch becomes available in the
  GitHub UI once the workflow is on the default branch.
- Every job uses **Ubuntu 24.04**. Backend/scanners use **Python 3.12**;
  frontend uses **Node 22 LTS** and its bundled npm. These are explicit supported
  release lines, not immutable OS images or patch-level pins. Frontend installs
  from `package-lock.json` with `npm ci`; backend requirements still contain
  version ranges, so backend dependency resolution is not fully locked.
- Main CI jobs have 25/30-minute limits; security jobs have 2–30-minute limits.
  Concurrency includes workflow, event and PR number (otherwise full ref): a
  newer run cancels only the same lane/event, not another PR or branch.
- Tokens have only `contents: read`; checkout does not persist credentials.
  No `pull_request_target`, write token, production environment or production
  secrets are used. Fork PR code runs only under the ordinary read-only PR event.
- Provider keys are explicitly empty in backend CI; model endpoints for Gemini,
  OpenAI and Anthropic resolve to loopback during tests. Existing tests use mocks
  and controlled pipelines. Package registries, advisory databases, Google Fonts
  at build time and browser downloads still require network access. This is not
  an entirely air-gapped workflow and provides no live-provider acceptance.

## Required checks

### backend

1. Install backend requirements, existing Ruff/pip-audit tooling and PDF libraries.
2. Ruff bug checks (`E9,F63,F7,F82`), not broad style enforcement.
3. Advisory pip-audit (all reported severities; not a high-only filter).
4. `alembic upgrade head` on a fresh PostgreSQL 16 service.
5. Default pytest unit suite, excluding integration via `pytest.ini`.
6. Explicit integration selection of `test_analysis_runs_integration.py`,
   `test_artifact_migration_integration.py`, `test_team_consent_integration.py`
   and `test_report_scope_integration.py`, with real PostgreSQL 16 and Redis 7.
   The Redis delivery test starts a real worker with controlled, non-provider
   pipeline output. Dedicated disposable Redis DB 14 is used for delivery.
   The JUnit report must contain tests and **zero skips**; absent services cannot
   silently downgrade this gate. These are not live S3 or production acceptance.

### CI-02 / issue #28: combined security verification

The manager assembled base `41026a521b77bdc3e55728a2b58b77886c797021`
from CI/build PR #22 and security PRs #23/#27 (Refs #18/#19/#25). CI-02
changes only this runbook, `ci.yml` and its workflow contract tests. Preserve
all prior agent attribution. Publish the combined branch as a **draft PR to
main**: stacked PR #27 targets the security branch and does not trigger these
main-target-only PR workflows. This is a verification vehicle, not merge or
deployment authorization. Security corrections still require independent review.

Both security fixtures require `ARTIPROOF_INTEGRATION_DATABASE_URL` pointing
explicitly to a dedicated migrated `postgresql+asyncpg://` database. CI provides
the disposable PostgreSQL service and runs `alembic upgrade head` before pytest;
no shared/local database, SQLite substitution or production credentials are used.
Consent fixtures use UUID-owned organizations/users and READ COMMITTED sessions
for actual lock contention and HTTP authorization; report fixtures use independent
sessions for persisted scope checks. Fixture rendering/email/provider stubs do not
replace the database. The existing real Redis delivery case remains selected.

The explicit `-m integration` overrides the default unit marker exclusion.
Unit-phase **deselections** are not service-suite **skips**. Record each JUnit
report's actual tests/failures/errors/skipped counts separately; do not infer
combined counts from earlier branches. Pytest exits remain fatal under Actions'
fail-fast shell; the subsequent JUnit guard rejects empty or skipped integration
reports. No conditional skip, failing-case deselection or timeout increase is
permitted. Failure artifacts retain reports and migration logs for seven days.

Regression-first local check: the new selection contract failed against the
assembled workflow because both security paths were missing. The JUnit guard is
also executed in subprocesses against nonempty, empty, skipped and malformed
synthetic reports. After adding the suites, rerun all workflow contracts,
actionlint and diff checks. Local contract checks are not PostgreSQL evidence.

Observe hosted backend/frontend on the exact published head with a bounded wait.
If application/security tests fail, download the run's failure artifacts/logs,
identify the exact test/error and route to SECURITY-01 (#19, consent/enrollment)
or SECURITY-02 (#25, report scope/schedules), or the responsible dependency lane.
Do not edit their files, suppress failures or call skipped downstream steps
passing. Record completed, failed or pending status in the PR/issue handoff;
a background watcher is not completion. No service restart, shared environment
changes, main merge or deployment is part of CI-02.

Migration logs and unit/integration JUnit reports are uploaded on failure for
seven days. GitHub step logs remain the evidence for install/lint failures that
occur before a report exists. Never attach environment dumps or secret files.

### frontend

1. `npm ci`, advisory `npm audit --audit-level=high`.
2. `npx tsc --noEmit`, `npm run lint`, all Vitest tests with JUnit output.
3. **`npm run build -- --webpack`**, a real production build including type and
   prerender checks. There is no compile-only or ignored-build-error shortcut.
   Webpack remains explicit for reproducible CI. An earlier Fraunces font-query
   failure on Node 26 Windows was intermittent: BUILD-01 subsequently retested
   default Turbopack successfully. This is not evidence of a persistent Turbopack
   failure. No package upgrades or application changes are required to select
   the CI bundler.
4. Install Chromium with Playwright system dependencies on Ubuntu 24.04.
5. Existing Playwright smoke tests run against **`npm run start`**, consuming the
   preceding build, not a dev server. CI never reuses an existing server. Local
   non-CI runs retain the existing dev-server behavior and explicit external
   server overrides. Public test-only NextAuth values require no production keys.

Failure artifacts include build logs, Vitest/Playwright JUnit, browser screenshots,
retained failure traces and the HTML report, where generated (seven days).
Playwright uses a nested output directory so browser cleanup cannot erase earlier
unit/audit/build evidence. Artifacts are diagnostic evidence, not deployment
packages.

## Security: availability is not clearance

Observed evidence at base `f551c5bada7ebcfabbc2c4a38fce11041812b150`:

- Main CI run **41312569623**: installed Playwright 1.60.0 rejected
  `ubuntu26.04-x64` after `ubuntu-latest` moved. Ubuntu 24.04 is supported by the
  installed Playwright; Node 22 also avoids the previous Node 20 engine warning.
- CodeQL run **41471312313**: both language analyses failed at upload because
  code scanning was not enabled. Repository metadata reports **private**;
  the code-scanning alerts API also returns HTTP 403 with that same enablement
  error. This is not proof that the code is safe, nor proof of the account's
  exact purchased entitlements. No billing/account-plan access was attempted.
- GitHub documents that private-repository code scanning needs a
  [GitHub Code Security license](https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning).
  An owner must confirm eligibility/enablement separately. Do not purchase a
  license, accept a trial or make the repository public as part of this task.

CodeQL remains visibly present. By default, its availability job emits a warning
and summary: **NOT SCANNED**, and the language jobs are skipped. This is not a
passing security scan. Only after owner confirmation of applicable licensing may
the owner set repository variable **`CODEQL_LICENSE_CONFIRMED=true`**. This worker
does not set it. Opted-in CodeQL v4 analyzes Python and JavaScript/TypeScript with
`security-and-quality`, producing downloadable SARIF artifacts with `upload:false`
and a read-only token. Disabling upload does **not** waive CodeQL licensing.
GitHub Security-tab alerts/PR annotations are not restored by artifact-only mode;
enabling that integration requires a separately approved configuration and token
permission review. A successful CodeQL analysis is not itself a zero-alert gate.

The separate **Security / Bandit (Python high severity / high confidence)** job
is a runnable nonlicensed substitute for a **limited Python** SAST gate:

```sh
python -m pip install bandit==1.9.4 PyYAML==6.0.3
bandit -r backend/app -lll -iii -f json -o bandit.json
python -c "import json; r=json.load(open('bandit.json')); assert not r['errors']; assert r['metrics']['_totals']['loc'] > 0"
```

Bandit uses the Apache-2.0 license and needs no account, provider key or GitHub
code-scanning entitlement. Matching findings, command failures, report errors,
skipped files and empty scans fail; reports are retained even on failure.
Bandit 1.9.4 is pinned deliberately: an initial local 1.8.6 attempt on Python 3.14
hit removed AST APIs and skipped files despite a zero exit. That attempt is not
clean-scan evidence. CI uses Python 3.12 and validates report completeness too.

**Remaining security gaps:** Bandit is not CodeQL-equivalent: lower severity or
confidence findings are not gated, and it does not scan JavaScript/TypeScript.
ESLint/unit tests are not a replacement for frontend SAST. A follow-up can add
Semgrep Community Edition with reviewed, locally pinned Python/JS/TS rules and
`semgrep scan --config <reviewed-local-rules> --metrics=off --error backend/app frontend/src`;
no paid Semgrep service or SARIF upload is needed. That broader substitute is
proposed, not implemented or verified here. Existing pip-audit/npm-audit checks
remain **advisory**, visibly warn on findings **or scanner failure**, and do not
establish a complete release security gate. Do not claim a green CI is CVE-free.

## Queue dependency compatibility follow-up

Hosted run **42239082260** at `be02b96662cd5fff50bd96e890d7d93f2d1796da`
passed migrations and 572 unit tests; real-service integration had 22 passes and
one failure in `test_real_redis_delivery_runs_without_a_stream`. A fresh isolated
Python 3.12.15 install reproduced its Celery 5.4.0 / Kombu 5.7.0 / redis-py 5.3.1
resolution and runtime `VersionMismatch`, without changing the shared audit venv.

Celery 5.4.0 declares plain `kombu>=5.3.4,<6.0` and its Redis extra declares
redis-py `<6.0`. Pip can therefore choose Kombu 5.7 without considering Kombu's
optional Redis extra. Kombu 5.7's transport requires redis-py >=6.1 at runtime,
and its extra metadata requires >=6.4. The installed redis-py 5.3.1 satisfies the
old direct requirements but cannot initialize that transport. **`pip check`
reported no broken requirements even with this runtime failure.**

Manager authorized a narrow production-requirements fix:

- `celery[redis]>=5.4.0,<5.5`: keep the verified 5.4 runtime rather than incidentally
  moving Celery to another minor while resolving the transport blocker.
- `kombu[redis]>=5.6.2,<5.7`: use the compatible 5.6 transport line and explicitly
  activate its Redis dependency metadata. Kombu 5.6.2 accepts redis-py
  `>=4.5.2,<6.5` excluding 4.5.5 and 5.0.2, compatible with the existing direct
  `redis>=5.2.1,<6.0` requirement, which remains unchanged.

These bounds apply to production installs, not a CI-only override. They hold the
current Celery/redis-py lines and replace the incompatible Kombu 5.7 resolution;
they do not fix all dependency advisories or fully lock transitive dependencies.
Review the bounds together when upgrading this queue stack, then rerun real
delivery. Raising redis-py's major version or upgrading Celery is not needed for
this bounded fix and was not performed.

`backend/tests/test_queue_dependency_compatibility.py` adds two default-unit
regressions: validate installed Redis-extra metadata for Celery/Kombu, and call
the actual Kombu Redis client-selection guard without constructing a broker
connection. Both failed against the original resolved stack before the fix.
They do not mock/suppress the version guard and do not replace the existing real
Redis delivery integration test. No application or security-owned tests changed.

Local follow-up verification on Python 3.12.15 in an isolated venv:

- Fresh queue resolution (`pip install --dry-run --ignore-installed --report ...`)
  selected Celery **5.4.0**, Kombu **5.6.2**, redis-py **5.3.1**.
- Reinstalling the full requirements changed only Kombu **5.7.0 -> 5.6.2**;
  `pip check` passed. Both no-network compatibility regressions then passed.
- Full default backend suite: **574 passed, 25 integration deselected**, with
  the existing 21 warnings. Ruff bug checks, five workflow contract tests,
  actionlint and `git diff --check` passed.
- Local broker/database integration was not run; the unchanged hosted real
  PostgreSQL/Redis gate must verify delivery on the new exact PR head. See PR #22
  for that run's outcome, including the separate expected BUILD-01 dependency.

## Verification and manager handoff

From the repository root with Python/PyYAML and actionlint installed:

```sh
python .github/workflows/tests/test_release_gates.py
actionlint -shellcheck= -pyflakes=
git diff --check
```

The contract tests were first observed failing against the original workflows
(missing dispatch/merge-queue support, production build, artifacts and license
opt-in), then made green. Actionlint validates Actions syntax/expressions; the
flags above explicitly omit optional shellcheck/pyflakes tools, not Actions
validation. Test files in subdirectories are not standalone Actions workflows.

Local CI-01 verification on axel-windows, 2026-11-06:

| Check | Observed result |
| --- | --- |
| Contract tests | 5 passed; initial missing-gate regressions and output-directory regression observed failing before their fixes |
| actionlint 1.7.12 | Passed; optional shellcheck/pyflakes not installed/enabled |
| Backend unit suite | 572 passed, 25 integration tests deselected; disposable interpreter is Python 3.14.9, not the CI Python 3.12 runtime; deprecation/async-mock warnings remain |
| Ruff 0.14.5 bug checks | Passed using an isolated tooling venv; shared backend interpreter dependencies untouched |
| Node 22.23.4 / npm 10.9.9 | `npm ci`, ESLint, TypeScript and 49 Vitest tests passed |
| Production webpack build | Compilation/type phase passed; build exited 1 at `/team` prerender (BUILD-01 dependency below) |
| Playwright | 11 tests discovered by `--list`; production browser smoke not run because the required production build failed |
| PostgreSQL / Redis / Alembic | Not run locally: no reachable dedicated services or Docker CLI; preserved in CI, not claimed passing |
| Bandit 1.9.4 | No high-severity/high-confidence findings, zero report errors, 17,177 LOC; report metrics include 10 low-severity findings outside the gate |
| Dependency audit | `npm ci` reported 30 vulnerabilities (2 low, 13 moderate, 11 high, 4 critical); no audit fixes/upgrades applied; pip-audit not rerun locally |

An initial Node 26/npm 12 unit command rejected forwarded reporter flags; the
Node 22/npm 10 rerun above is the successful supported-runtime evidence. Local
tool downloads/venvs are outside the repository and do not modify application
dependencies. Hosted results must still be reviewed on the PR.

**Integration dependency:** BUILD-01 / issue #17 owns the existing team-page
prerender defect. CI-01 must not edit that page or suppress its build failure.
Until the manager integrates BUILD-01's reviewed fix, the new frontend production
build is expected to fail on that route and production smoke cannot be accepted.
Manager should merge BUILD-01 first or bring its reviewed commit into the
integration lane, rerun backend/frontend on the combined head, inspect artifacts
and get independent review. Do not merge CI-01 just because its unit tests pass.

Local Windows tests are not Linux service/runner evidence. Use the draft PR's
exact head SHA, commands/results and remote runs for the current evidence record.
No merge, deployment, visibility, billing or branch-protection changes are made
by CI-01. Rollback is a manager-reviewed revert of the CI/config commit; preserve
required check names and do not weaken protection as a workaround.
