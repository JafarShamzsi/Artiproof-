# Authenticated pilot QA: QA-02 bounded ownership repair

Agent-Tag: QA-02. Device-Tag: axel-windows.
Authority: [issue34 comment6710508226](https://github.com/JafarShamzsi/ArtiProof/issues/34#issuecomment-6710508226).
Isolated branch: `agent/qa-02/process-ownership`, worktree
`D:/Developer/ArtiProof-worktrees/qa-02`.
Assigned base: `d1fb4837e6abb9fc46606d4075894a2761fc30d0`.
Regression-first commit: `a494a6c`; repair/test commit:
`8de4e559aee4f0edf5d97e53590dad471c908265`.

**Status: STOP for fresh independent review of the exact published successor SHA.**
QA01/PR43 remain frozen and historical. Separate main-target draft required;
the PR handoff identifies the final documentation-inclusive local/remote SHA.
No source-safety self-approval, runtime acceptance, integration, issue closure or
authorization to run services is implied. Manager alone owns integration.

## Current QA-02 scope and lifecycle contract

Only these six paths changed relative to the assigned base:

- `scripts/qa_auth/owned_process.py`
- `scripts/qa_auth/lifecycle.py`
- `scripts/qa_auth/probe_owned_process.py`
- `scripts/qa_auth/test_final_safety.py`
- `scripts/qa_auth/test_cleanup_regression.py`
- `docs/AUTHENTICATED-QA.md`

The independent review's four mock failures were reproduced before repair:
unassigned-root termination failure, failed wait/poll, asynchronous termination
timeout, and the caller falsely treating the resulting closed-object no-op as
successful cleanup. Closing process/thread handles does not terminate a root;
closing an unassigned Job does not own that root either.

Exit confirmation and handle closure are now separate facts. The root needs a
signaled wait, and an assigned Job needs zero active processes. Stop attempts
termination without requiring a successful initial root poll. Termination,
root wait, descendant confirmation and safe handle release are independently
attempted. The first error retains its type; later errors remain diagnostics.
`WAIT_FAILED` remains a Win32 error, not a timeout. Independently releasable
auxiliary resources are still attempted after root-cleanup failure.

Unconfirmed roots retain their exact process/thread handles; unconfirmed assigned
trees retain the Job handle. `close()` refuses to discard these handles, and
`stop()` cannot report success from a closed-but-unconfirmed object. Only confirmed
exit plus complete handle release permits `cleanup_complete` and inventory state
`exit-confirmed-handles-closed`. A colliding/preexisting Job is never configured,
queried as our tree, adopted or terminated, including repeated close failures.

Constructor abort has one root-stop attempt, then transfers retained ownership
through `ProcessConstructionError`. `RunOwner` has at most **two further stop
attempts total**, across all phases; repeated cleanup cannot reset that budget.
The existing finite sealed sweep and later container/log/evidence attempts stay
intact. Both probe tests now use `RunOwner.start()` with `finally` cleanup; there
is no remaining direct production constructor caller outside the owner's factory.
Probe adaptation was inspected by AST only, never imported or executed.

Exhausted cleanup records `cleanup-unresolved`, disposition
`unresolved-budget-exhausted`, root/tree/handle confirmation facts, and per-attempt
diagnostics. `checks.json` includes `unresolved_processes` and stays failed. A later
successful retry does not erase the original command/construction failure or
earlier cleanup diagnostics.

**Unresolved is not recovered.** Permanent OS failures can leave a live suspended
root or descendants unreconciled after the finite attempts. Handles are retained
only while the owner object/runner lives; runner exit or hard kill can abandon an
unassigned root. No guarantee of eventual termination, interrupted-run recovery,
safe PID replay, or automatic manual intervention is made. Keep the failure and
request separately authorized manager disposition; never kill a PID from inventory.

## Current QA-02 validation (mock/static only)

All generated artifacts are under
`C:/Users/Axel/AppData/Local/hermes/cache/scratch/qa-02/`.
The existing QA01 Python interpreter was used read-only with `-B`; no dependency
installation, environment mutation or other-worktree write was performed.

`safe_suite.py` directly loads `test_*.py`, redirects `run.SCRATCH` in memory,
and rejects actual subprocess creation, shell execution, socket connection/DNS,
socket binding and native DLL loading through an audit hook. It does not load
`probe_owned_process.py` or invoke any supervisor/probe wrapper. Commands:

```powershell
$py = 'C:/Users/Axel/AppData/Local/hermes/cache/scratch/qa-01/venv/Scripts/python.exe'
$runner = 'C:/Users/Axel/AppData/Local/hermes/cache/scratch/qa-02/safe_suite.py'
& $py -B $runner four-red             # BEFORE repair: 4 assertion failures
& $py -B $runner full-publish         # AFTER repair: 69 passed, zero skips
& $py -B -m ruff check --no-cache --select E9,F63,F7,F82 scripts/qa_auth/owned_process.py scripts/qa_auth/lifecycle.py scripts/qa_auth/probe_owned_process.py scripts/qa_auth/test_final_safety.py scripts/qa_auth/test_cleanup_regression.py
```

| Evidence | Actual result |
| --- | --- |
| `four-red.log` | Four tests, four assertion failures, zero errors/skips before repair. Not import or infrastructure failures. |
| `four-green.log` | Same four regressions passed after repair. |
| `full-publish.log` | 69 Python methods passed, zero failures/errors/skips: inherited 49 plus 20 QA02 regressions. Includes AST parsing and static probe-caller checks. |
| Required Python error lint, `--no-cache` | Passed for all five changed Python files. |
| `git diff --check` and protected-path diff | Passed; no browser/config/journey, application, manifest, workflow, runtime, run.py or original six-guard changes. |

Earlier artifacts are retained: initial full suite 53 passed, expanded suite 66
passed. `full-final.log` recorded one mocked API-dispatch error in 69 methods:
an added final-state check initially misclassified a deliberately running owned
service before finalization. Restricting that check to finalization corrected the
assumption; the inherited API-only mock test then passed. Mocked stdout labels
`migrations` / `auth-api` are NOT executed service or AUTH validations.

The six Node offline checks were **not rerun**: this isolated worktree has no
TypeScript/node_modules dependency. No install or dependency link was authorized
or attempted. Their historical green result is not promoted to QA02 evidence.
No frontend types/lint/build, pip check, browser collection, actual native/process
probe, Docker command (even info), server, container, live network/provider test,
AUTH/CONTRACT check, secret/.env/customer/production read, merge/rebase/deploy or
other-worktree execution was performed. No global resource inspection or current
host/engine cleanup-state assertion is made.

**Browser hard hold unchanged:** browser modes, auth config, fixture and policy
still refuse. Known automatic-redirect escape remains unresolved. Lifting the hold
requires an independent containment design and explicit manager permission in a
later reviewed source change, not this cleanup repair. Existing journey failures
and unreached acceptance remain unwaived.

## Historical QA-01 record (frozen, not current authorization)

Everything below is retained attribution/evidence from QA01. Its old commands,
permissions and green results are historical, not permission to run them in QA02.

### Authenticated pilot QA (QA-01)

References: [#34](https://github.com/JafarShamzsi/ArtiProof/issues/34).
Agent-Tag: QA-01. Device-Tag: axel-windows. Baseline:
`e1372a722b2f4e25ff38505238c62b93d0af49ad`.

**Status: BLOCKED. Second/final safety correction; stop for independent review.**
Manager directive:
[PR43 comment 6697007564](https://github.com/JafarShamzsi/ArtiProof/pull/43#issuecomment-6697007564),
base `5c590968461820cb1e8196e3c05f862470dd9846`.
Do not run Docker/container/server/browser lifecycle or actual process probes.
Do not retry paused AUTH/CONTRACT validation. Any unresolved safety defect after
this final automatic correction must be escalated, not automatically retried.

**Executable browser hold:** `all`, `tracer`, `resources` and harness `smoke`
refuse before artifacts/process/port/Docker setup. The auth Playwright config
also refuses direct invocation, including `--list`; fixture/policy helpers hold
as well. There is **no** environment/CLI permission switch. Lifting the hold
requires an **independent containment design plus explicit manager permission
in a later reviewed source change**, not just approval to rerun this harness.

Known installed Playwright **1.60.0** limitation confirmed by independent review:
automatic external redirects bypass the route callback; the denial list can stay
empty while the external request escapes. Request routing is **not egress
containment**. No proxy/firewall/containment redesign or bypass is introduced here.

Earlier manager correction:
[6695328018](https://github.com/JafarShamzsi/ArtiProof/pull/43#issuecomment-6695328018).
The old head `b837cf498aba152d7f17278ef935aa9c38765836` had unsafe cleanup and an
unconstrained Docker context. Its historical thin tracer passed, but those runs
are **not** safety/runtime acceptance for the successor code. The old invitation
browser failure is recorded in [#41](https://github.com/JafarShamzsi/ArtiProof/issues/41);
AUTH-02 owns that application fix in a separate worktree, not this correction.
Do not turn that test into a skip, expected failure, or mocked route response.
No production application edits, merge, or deployment belong to this lane.

## Scope and isolation

- Separate `frontend/playwright.auth.config.ts` retains `testDir: ./e2e-auth`.
  The default smoke config and `frontend/e2e/` are unchanged. Historical
  collection was **3 auth / 11 default smoke**; current auth collection is held,
  not passed. The harness `smoke` mode is held too; the default smoke config
  itself is outside this correction's ownership and is not a global browser ban.
- Actual Next.js UI, NextAuth credential provider, FastAPI routers, bcrypt/JWT,
  persisted sessions, email tokens, membership, authorization, SQLAlchemy and
  Alembic migrations. No auth dependency overrides, manufactured authenticated
  identity, browser route fulfillment, or substituted authorization endpoints.
  Browser execution is now refused; the retained interception code is unreachable
  through the held helper and is not a containment claim. No route is fulfilled
  and no authentication response is rewritten.
  Malformed/unsigned tokens are used only as negative inputs that must fail.
- Only email **delivery** is replaced, before routers import it. Real tokens
  and rendered links go to a test-owned filesystem mailbox. No Resend delivery
  or external mailbox verification is claimed. Users have random `qa01-` emails
  at `example.com` and newly defined synthetic passwords, never existing accounts.
- Intended later approved mode checks **3203 / 8203 / 55443 / 56443** before binding.
  It is Windows-only and pins **every** Docker command to
  `--host npipe:////./pipe/docker_engine`, plus `--config` pointing to a fresh
  run-owned empty directory. No ambient context, DOCKER_HOST/CONTEXT/CONFIG,
  remote TCP/SSH or other platform fallback is supported. Unsupported targets
  fail before spawn. A bounded `info` checks the chosen pipe's Linux engine,
  not an ambient/default context. No Docker config/credential file is read.
  The proposed lifecycle creates
  random-name, labeled, loopback-only disposable PostgreSQL 16 / Redis 7
  containers with `docker run`, never root/shared Compose. PostgreSQL uses tmpfs;
  containers are `--rm`. Images are digest-pinned in `scripts/qa_auth/run.py`.
- Historical service runs migrated from empty through **0018_analysis_runs**. Later readiness
  requires both real PostgreSQL and Redis. No SQLite substitution. Resources and
  queues disappear with these owned containers, not shared-table truncation.
- Backend configuration is imported with Pydantic `_env_file=None`. The child
  environment uses a non-secret allowlist, not copied ambient API credentials.
  Next startup refuses project dotenv files by metadata only. No root `.env`,
  credential store or customer data is read; no other worktree is modified.
- **Network bounds, not an egress sandbox:** Python's `getaddrinfo`/socket `connect`
  patch is only a best-effort tripwire in that process. It does not cover native
  SDK sockets, `connect_ex`, UDP, child processes, Next/Node or OS traffic.
  Credentials are stripped, telemetry disabled and app/database/Redis URLs fixed,
  but those are not comprehensive network containment.
- **Known redirect escape, not merely untested:** the old HTTP/WebSocket routing
  policy allows local destinations, but automatic HTTP redirects escape its
  callback in installed Playwright 1.60.0. A zero-length denial list does not
  prove containment. Blocking service workers does not fix this redirect escape.
  The selected mitigation is the unconditional browser hold above; no new
  containment architecture is attempted.
- Standalone Playwright API contexts do not inherit browser routing. The new
  wrapper validates the same exact local HTTP origins before the real method
  call and forces `maxRedirects: 0`; all authored `page.request` calls use it.
  Python HTTP tests use a fixed local base, `trust_env=False`, and HTTPX's default
  no-redirect behavior. Next/backend/native libraries are not governed by the
  browser policy. Broader OS sandboxing requires separately approved ownership.
  No worker/model output is faked; no worker or paid provider runs in this pass.
- Historically, each browser file got a fresh owned API process (real limiter buckets, no
  limiter bypass or forwarded-IP forgery). The independent HTTP suite gets
  another fresh owned API process against the same disposable database.
- Ownership is persisted in `inventory.json` **before** spawn/create: random run
  and resource identity, exact intended container name/labels and process Job name.
  Process creation is suspended until Windows Job assignment and durable PID /
  creation-time metadata succeed. Live kernel Job/process handles, **not recorded
  PIDs**, authorize termination. No breakaway flag is set; the non-inherited Job
  handle uses kill-on-close. Cleanup also reaps descendants after a root exits.
- Container preflight refuses an already existing exact name, even if labels
  happen to match. A reported name-conflict race after preflight also refuses
  adoption/stop. Ambiguous creation stays tracked; cleanup inspects **only**
  that exact name's ID/name/labels/state (never environment/credentials). All
  run/resource labels must match before stopping its immutable ID. No global
  label/pattern/port lookup or cleanup is authorized. A timeout with no observed
  resource remains **uncertain**, not a confirmed absence; manual exact-identity
  reinspection requires approval. No blind PID/container replay from inventory.
- Every inspect/exec/stop and process wait/Job cleanup is bounded. Cleanup attempts
  continue individually after errors, aggregate diagnostics with the original
  failure, and write `checks.json` independently of resource cleanup errors.
  Uncertain cleanup makes the run fail. A hard-killed runner can leave containers;
  inventory is diagnostic only. No automated interrupted-run recovery is claimed.
  The final correction seals spawning during the final sweep and limits each
  tracked process to **two owner-level stop attempts in total** across command,
  start-failure and cleanup phases. The finite final sweep includes processes
  created by container cleanup, including failed starts. Earlier failures remain
  diagnostics even if a later close succeeds. Exhaustion/retained handles fail.
- A native constructor deletes an attribute list only after successful
  initialization. Duplicate standard handles remain on the owned object until
  confirmed closed. A first auxiliary-close failure is diagnostic, not silent
  success: construction aborts, stops the suspended/assigned/resumed owned root,
  and makes one further auxiliary release attempt. If handles remain, the raised
  error carries that owned object to `RunOwner`, preserving bounded later cleanup.
  Thus a permanently failing duplicate has at most **two constructor attempts
  plus two owner attempts**, never blind/recycled-PID cleanup or an unbounded loop.
  Logs, synthetic email/token payloads, PDFs, traces and screenshots stay under
  `C:/Users/Axel/AppData/Local/hermes/cache/scratch/qa-01/`. Do not treat synthetic
  trace tokens as real credentials or reuse the test signing keys anywhere else.

## Commands, subject to the current no-lifecycle boundary

**Currently permitted:** direct Python mocked tests, Node offline mocked policy
checks, AST/type/lint checks using existing dependencies. Do not invoke the
`RunOwner`/Win32 process-probe wrappers for validation during this final pass.
**Do not run** actual Docker commands (even `info`/`inspect`), services, browsers,
`harmless-probes`, app builds or AUTH/CONTRACT approval-blocked probes.
The existing `api` mode remains an API-only command path, verified here only
with mocks. It is not authorized to execute now and cannot certify browser
journeys. Browser-dependent modes are additionally refused by source code.

```powershell
$py = 'C:/Users/Axel/AppData/Local/hermes/cache/scratch/qa-01/venv/Scripts/python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:QA_AUTH_ARTIFACTS = 'C:/Users/Axel/AppData/Local/hermes/cache/scratch/qa-01'
& $py -B -m unittest discover -s scripts/qa_auth -p 'test_*.py' -v
node --test frontend/e2e-auth/network-policy.check.mjs
# No probe_owned_process.py execution: all Win32 failures are Python mocks.
```

Historical setup/service reference ONLY (not current authorization; browser
modes below now refuse and have no bypass). Prerequisites: Docker Linux engine, Node/npm, Python with repository
backend requirements, and lane-owned `frontend/node_modules`. Do not link another
lane's dependencies, install globally, or change shared services.

```powershell
# From this worktree. Use an installed Python to create an OWN scratch venv.
python -m venv C:/Users/Axel/AppData/Local/hermes/cache/scratch/qa-01/venv
$py = 'C:/Users/Axel/AppData/Local/hermes/cache/scratch/qa-01/venv/Scripts/python.exe'
& $py -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
npm --prefix frontend ci --no-audit --no-fund
$env:PLAYWRIGHT_BROWSERS_PATH = 'C:/Users/Axel/AppData/Local/hermes/cache/scratch/qa-01/browsers'
node frontend/node_modules/@playwright/test/cli.js install chromium

& $py scripts/qa_auth/run.py tracer           # first thin, real UI-to-backend tracer
& $py scripts/qa_auth/run.py all              # all 3 browser slices + real HTTP tests
& $py scripts/qa_auth/run.py api              # only real HTTP/service integration
& $py scripts/qa_auth/run.py resources        # independent personal resource browser slice
& $py scripts/qa_auth/run.py harness-checks   # harness safety/compile tests + pip check
& $py scripts/qa_auth/run.py unit             # complete default backend unit suite
& $py scripts/qa_auth/run.py frontend-checks  # unit, types, changed/full lint, build, collection
& $py scripts/qa_auth/run.py smoke            # unchanged default smoke, not authenticated E2E
```

Do not run Next builds and browser/dev-server checks concurrently in this tree.
The runner does not install dependencies or change global configuration. Each run
prints a unique evidence directory containing `checks.json` and command logs.
Failures do not become passes. `all` now refuses browser execution immediately.
Lower-level result aggregation still retains a red check while independent
mock checks execute; no actual browser workflow is run. No test retries are configured.
Absent Docker/services, occupied ports, missing browsers, migrations or assertions
are hard failures, not skips. Preserve the evidence directory and report the exact
unavailable acceptance. Never kill a PID from disk: it may have been recycled.
After a hard kill, request manager review of exact intended resource metadata;
inventory alone is not ownership authorization. There is no recovery executor.

The runtime also supports `pytest` for focused checks, but requires the runner's
explicit isolated environment. The new backend module is `integration`-marked;
the default unit suite intentionally excludes it. Direct opt-in without
`QA_AUTH_ARTIFACTS` fails with a blocked message rather than silently skipping.
Do not run the whole auth suite directly against an already-running API: repeated
signup/login tests share real IP rate limits. Use the owned lifecycle above.

## Second/final correction evidence (base 5c59096, mocks/static only)

No actual Docker, container, server, browser, native process probe, provider call,
install, app edit, AUTH-02 worktree operation or paused AUTH/CONTRACT validation
was performed. Existing journey assertions were not edited. No containment
redesign was attempted. Source safety still requires independent re-review.

Regression-first `test_final_safety.py` at the blocked base reproduced all three
findings using Python mocks only: **7 test methods, 10 failing assertions/subtests**,
including four browser modes. Red artifact:
`scratch/qa-01/final-safety-red-6697007564.log` (PowerShell UTF-16 text; retained).
No Docker/native process was spawned by those reproductions.

The focused regressions cover a resumed cleanup-created process followed by an
inventory write failure, a cleanup-command close failure requiring a final retry,
permanent failure budgets, and continuation to later containers/evidence with
the original error preserved. Fully mocked Win32 constructor tests cover failed
second initialization, successful initialization followed by failure, assigned /
unassigned suspended roots, resume/persist failure, transient and permanent
duplicate closes, and propagation of retained ownership to the caller. A final
sweep cannot spawn recursively. Existing API-only dispatch is tested with **all**
lifecycle calls mocked, not by running the HTTP service suite.

Current Node checks verify unconditional holds before context routes and auth
configuration, absence of an argument/environment permission override, and the
unchanged exact-local API wrapper with redirects disabled. Previous mocked
interception checks were not evidence against the known automatic-redirect
escape; they have been replaced by hold assertions. Actual journey assertions
remain unchanged and unreachable for later controlled acceptance.

Final safe results for this correction: **49 Python mocked tests passed**
(33 inherited, with hold/retry expectations updated, plus **16 new regression
methods**), **6 Node checks passed**, TypeScript, changed-file ESLint and required
Python error lint, full frontend ESLint and `pip check` passed. No test skips in the Python/Node mock suites. The
original six guard tests remain unchanged; they alone do not establish safety.

| Current evidence under `scratch/qa-01/` | Scope/result |
| --- | --- |
| `final-safety-red-6697007564.log` | Regression-first blocked base: 7 methods, 10 failing assertions/subtests. Fully mocked; UTF-16 PowerShell log retained. |
| `final-safety-focused-6697007564.log` | Initial focused 7 methods passed after fixes, before added failure-path coverage. |
| `final-safety-full-final-6697007564.log` | Full 49-method mock suite passed; labels `migrations` / `auth-api` in stdout are mocked command names, NOT executed service validations. |
| `final-safety-job-collision-red-6697007564.log` | Additional constructor collision regression initially failed (16 focused methods, one failure): an unassigned/preexisting Job reference must not be queried as an owned tree. The final code queries descendants only after successful assignment, and this regression passes. |

No production build, real browser collection, native process probe, real API
acceptance or approval-blocked AUTH/CONTRACT probe was run. Initial type checking
found unreachable-flow narrowing errors after adding the unconditional config
hold; an expression-level required-artifact check fixed them. No browser or
framework runtime was used to correct that static error.

Exact successor SHA and final static command results are in the PR handoff. Python
tests are direct `unittest` discovery, not `run.py harness-checks`; no actual
process/Job probe is repeated. The earlier 33-test result, six routing mocks and
two harmless Job probes below are **historical first-correction evidence only**,
not acceptance of these newly reviewed failure paths or permission to rerun them.

## Historical first-correction evidence (blocked head 5c59096)

The earlier candidate at 5c59096 was subsequently **blocked** by the second review
findings above. The following are its historical reported results only, not new
validation of the final correction. No Docker command (including `info`, `inspect` or `ps`),
container, server, browser launch or service-backed harness run was performed
during this correction. No application/AUTH-02 worktree, manifests or workflows
were changed. The following are safe checks, not E2E or a new runtime verdict:

- Regression-first against `b837cf4`: two fully mocked `main()` reproductions
  failed as expected (missing evidence/cleanup after stop timeout; untracked
  creation timeout). Raw log: `scratch/qa-01/correction-red-20261107.log`.
  The old stop failure also leaked a mocked test log handle; this is recorded,
  not counted as a third production failure or a pass.
- `test_harness.py` retains the **six old guard tests** unchanged. Those six alone
  never established lifecycle safety. `test_cleanup_regression.py` adds focused
  **fault/ownership tests**: ambiguous creation after a mocked side effect,
  stop/inspect timeouts and nonzero exits, original-error preservation,
  cleanup/evidence continuation, multiple error aggregation, ownership mismatch,
  preexisting/name-race collision refusal, exited parent, durable pre-resume
  identity, unsupported mode/endpoint rejection, environment-independent Docker
  command targets, bounded commands, no-proxy/no-redirect readiness, and an
  entirely mocked `main(all)` preserving red-journey exit while later independent
  checks execute. Final result: **33 Python tests passed = 6 old guards + 27 new
  fault/ownership/readiness tests**, no skips. `pip check` also passed.
- `node --test frontend/e2e-auth/network-policy.check.mjs`: **6 mocked checks
  passed**, no browser or URL contacted. They verify HTTP abort before dispatch,
  the context handler's use for later-page requests, local auth `continue`
  without fulfillment, WebSocket rejection before connection, standalone API
  target rejection and forced zero redirects. Real browser interception,
  redirects and service-worker behavior remain unperformed acceptance.
- `run.py harmless-probes`: **2 harmless Windows Job probes passed**. An owned
  Python parent spawns a sleeping child then exits; Job cleanup reaps descendants
  while a second owned Job stays running. Another probe forces identity-write
  failure before resume and confirms no child instruction writes its marker.
  Probe artifacts persist under scratch. This does not prove container/real
  service, forced-runner-kill or host-restart recovery.
- `run.py safe-checks`: **72 frontend unit tests passed, 1 existing opt-in
  BUILD-02 network-denied webpack build skipped**; types, auth-file/full ESLint,
  collection and the 6 Node policy checks passed. Collection remains **3 auth /
  11 default smoke declarations**; neither browser suite ran. No local app build
  was run in this correction because the boundary is safe mocks/static only.
- Python changed-file required error lint and AST compilation passed; `pip check`
  reported no broken requirements. Initial harmless probe assertions completed
  but their automatic temporary-directory deletion hit a log-handle timing error;
  bounded termination waits and retained probe artifacts replaced immediate
  deletion, and subsequent probes passed. The initial failed log remains
  `scratch/qa-01/correction-harmless-probes-20261107.log`, not passing evidence.

All paths above use prefix `C:/Users/Axel/AppData/Local/hermes/cache/`.
No old service artifact is rewritten or promoted to successor acceptance. The
new helper/mock tests are manual safe-check entry points, not added to default
smoke, Vitest source collection or hosted authenticated CI.

| Correction command | Evidence under `scratch/qa-01/` | Actual scope/result |
| --- | --- | --- |
| `run.py harness-checks` | `20261107-012543-d6a4f4db` | 33 Python tests, pip check; original error plus cleanup diagnostics preserved in mocked failure cases. AST compile is included. |
| `run.py safe-checks` | `20261107-011821-08046911` | 72 frontend unit passed / 1 opt-in build skipped; types, changed/full lint, 3 auth / 11 smoke declarations, 6 mocked Node policy checks. No build or browser suite execution. |
| `run.py harmless-probes` | `20261107-011821-78c7f8e4` | 2 harmless nested Windows Job probes passed, logs plus run inventory/checks retained. Each probe also prints its own retained scratch directory. |
| `python -m ruff check --select E9,F63,F7,F82 scripts/qa_auth` | Tool output recorded in successor handoff | Passed. No application code lint/runtime acceptance implied. |

The correction does not re-run the historical 693-test backend suite or production
build, because application code is unchanged and this pass excludes service/build
lifecycle. Normal hosted CI may run its existing checks after publication, but
does not execute the new manual fault tests, Windows probes or authenticated suite.
An additional regression caught the old Popen-specific `returncode` access in
readiness while adapting to owned handles (`20261107-012435-76219b2d`, one failure).
Readiness now reports the handle's `poll()` exit code; its regression passes in
the final 33-test run. This was a mocked/static correction, not a service run.

## Historical local results at blocked head b837cf4 (2026-11-07)

These artifacts are preserved, not rewritten. They predate correction and prove
neither corrected lifecycle safety nor successor service/browser acceptance.

Environment: Windows, Python **3.14.9**, Node **26.13.0**, lane-owned dependencies;
CI uses different pinned Python/Node versions. Evidence prefix below is
`C:/Users/Axel/AppData/Local/hermes/cache/scratch/qa-01/`.

| Command / evidence directory | Actual result |
| --- | --- |
| `run.py tracer`, `20261107-001329-82028615` | First real tracer **1 passed**: UI registration 201, real NextAuth login, `/api/auth/me` 200, anonymous 401, logout 204, same bearer rejected 401. |
| `run.py all`, `20261107-003158-56b62140` | **Exit 1**, deliberately not green: tracer **1 passed**, invitation **1 failed**, independent personal resource browser **1 passed**, HTTP integration **3 passed**. Migration/readiness and cleanup commands exited zero; complete-tree/failure-path cleanup was NOT established by that run. |
| `run.py api`, `20261107-003602-60c6d8b2` | Final strengthened HTTP suite **3 passed**, no skips: includes verified wrong recipient rejected, foreign-session revocation rejected, and extracted PDF text preserving `unavailable`. |
| `run.py unit`, `20261107-003801-e2e84f3f` | Final **693 passed, 144 integration deselected**, exit 0. These deselections are NOT real-service acceptance. Existing Python 3.14/dependency deprecation warnings remain. Earlier lane-owned run `20261107-002222-3d97432a` also passed. |
| `run.py harness-checks`, `20261107-003800-a83fcb35` | Final **6 safety/compile tests passed**, `pip check`: no broken requirements. |
| `run.py frontend-checks`, `20261107-003314-8c40b2d8` | **72 unit/component passed, 1 skipped**; TypeScript, auth-file ESLint, **full ESLint**, production Turbopack build, auth/default collection all exit 0. The skipped existing BUILD-02 opt-in network-denied webpack build was not run. |
| `run.py smoke`, `20261107-003426-3582345d` | Unchanged default smoke **11 passed**. This is not evidence for authenticated journeys. |

Python changed-file required error lint also passed:
`python -m ruff check --select E9,F63,F7,F82 scripts/qa_auth backend/tests/test_pilot_auth_journeys.py`.
`git diff --check` passed. Test/harness source slice is commit `58a1e91`;
the draft PR/handoff identifies the final documentation-inclusive head SHA.

Earlier failures are retained, not erased: initial Chromium was absent; a
lane-scoped browser install resolved that infrastructure blocker. The borrowed
read-only audit venv failed two queue dependency checks (Kombu 5.7 with redis-py
5.3.1); it was not modified. Fresh lane requirements resolved those checks.
Harness development also exposed/corrected a URL-safe-token regex truncation,
an incorrect inferred Team billing-tier assertion (membership preserves `free`),
cached-PDF header expectations and onboarding/tab locator races. Those failed
attempts are not application defects or passing acceptance evidence.

### What those historical real tests observed (not successor acceptance)

- Signup persists a researcher, including downgrade of a requested public admin
  role. Credential login creates real revocable backend sessions. Anonymous and
  malformed/unsigned bearer requests fail. A different user cannot revoke another
  account's session; explicit session revocation kills that token, not other logins.
- Unverified invite acceptance fails. A **verified wrong email** also fails.
  Preview does not enroll. Real email verification consumes a single-use token,
  replay fails. Explicit acceptance/replay yields one current enrollment; removal
  clears `/me` organization and denies organization member-list access. An accepted
  invite cannot re-enroll the removed member.
- Real UI text submission persists a **pending** source. **201 does not prove
  Redis task publication**: the application catches broker publication failures.
  No independent broker assertion was made. Real report-generation/list/download routes produce an unassessed PDF;
  HTTP PDF text extraction confirms `unavailable`. The independent browser checks
  actual Reports UI listing and PDF bytes through real authorized API calls.
- Source/report reads and downloads permit the owner and current org admin,
  reject an outsider and anonymous requests. After explicit logout the same token
  cannot read source/report/download routes. The browser's still-existing
  NextAuth cookie cannot restore backend access and the UI returns to `/login`.
- Org creation/inviting/removal and report generation/download portions use actual
  HTTP clients in the browser harness, not every control in their UI. Only the
  verified invitation's review/accept and personal source submission are clicked.
  Do not relabel this mixed UI/API coverage as a complete all-controls UI journey.

## Blocked / untested acceptance and next owner

| Gate | Status / next scope |
| --- | --- |
| Verified invitation browser success + navigation/session continuity | **FAILED / blocked by #41**. Backend enrolls and NextAuth refresh succeeds, but `/register?invite=...` resets to Review invitation. Manager assigns `frontend/src/app/(auth)/register/page.tsx` and `frontend/src/components/invitation-consent.tsx`; QA lane cannot edit them. The remaining steps in `journey.spec.ts` are unreached, not passes. Independent browser/HTTP slices do not waive this failure. |
| Post-invitation team controls and removal using actual team UI | **Untested**. Removal and scoped access are proven by real HTTP only. Manager assigns UI acceptance after #41. |
| Removal versus continued direct-owner access to organization-scoped work | **Policy acceptance untested**. Current ownership helper permits direct owners. Tests prove membership removal and explicit logout denial separately, not automatic revocation of all sessions or former-owner access on removal. Manager must define required policy before expanding this gate. |
| Corrected lifecycle runtime acceptance | **NOT RUN / prohibited pending independent re-review**. Current Win32 tests are mocks only; old harmless process probes are historical. API-only runtime needs separate permission. Browser modes are hard-held until an independent containment design and explicit manager permission in a later reviewed source change; cleanup review alone does not lift that hold. |
| Completed source/researcher pipeline, worker execution, progress/recovery, model quality | **Blocked/unverified here**: no Celery worker, coordinator execution, provider fixtures or model calls. Pending sources and unassessed reports are not completed analyses. Next lane must add approved test-only provider fixtures plus real worker lifecycle, without mocking auth or routes. Redis health is not publication or consumption evidence; pending 201 proves neither. |
| Styled WeasyPrint PDF | **Unavailable locally**: native GTK/Pango missing; backend logs plain-text PyMuPDF fallback. Cached download header is `cached`, not renderer proof. PDF access/content tests do not validate styled layout. |
| Google-only/OAuth accounts, linked-provider edge cases | **Untested**, no real external account or credentials authorized. |
| 2FA/TOTP/backup-code journeys | **Untested** by this authenticated suite; existing component/unit tests are not substitutes. |
| External email/identity verification deliverability | **Untested**; only the synthetic delivery sink and real internal verification-token consumer run. |
| Hosted execution of this new auth harness | **Not wired**. Owned paths exclude `.github/workflows/ci.yml`; normal CI excludes this integration module and uses the default smoke config. Green component CI cannot satisfy #34. Manager must own any future isolated auth CI integration. |
| Production/customer/paid-provider acceptance | **Not authorized or attempted**. No merge/deploy or pilot-ready claim. |

### Defect evidence

[#41](https://github.com/JafarShamzsi/ArtiProof/issues/41) contains a published
screenshot and exact routes/assertion. In the final `all` directory, inspect
`browser-journey.log` and
`playwright/journey/journey-real-verified-invi-f19cd-and-revoked-browser-session-authenticated-chromium/`
for `trace.zip`, `test-failed-1.png`, and `error-context.md`.

Source-level explanation for manager review: NextAuth `update()` sets session
status to `loading`. The register page's authenticated-only branch changes the
position of `InvitationConsent`, unmounting its local invitation/accepted state
during refresh. A real 200 session refresh with the correct organization ID still
leaves a remounted Review invitation UI. The regression stays failing until an
independently assigned application fix is verified.

Handoff must identify the exact pushed SHA and draft PR separately; reviewing an
earlier SHA does not approve a later commit. No auth suite skip/waiver, component
CI result, or successful thin tracer authorizes integration of an unreviewed tree.
