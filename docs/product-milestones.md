# Product delivery milestones

Updated: 2026-11-01. Goal remains active.

The detailed scope and release gates are in
[the readiness assessment](product-readiness-analysis-2026-10-24.md).
This log tracks implementation evidence, not assumed completion.

| Milestone | Deliverables and acceptance | Status |
|---|---|---|
| M0: Development readiness | Runnable Python/backend tests, frontend checks, required skills/tools assessed | Complete for local development: latest checks record 572 backend and 49 frontend unit tests passing; TypeScript/changed-file lint pass. Python, dependencies, skills and headless Chromium installed. No additional MCP required. Real integration infrastructure remains an M2 gate. |
| M1: Honest pilot results | Public claims match capabilities/quotas; missing evidence cannot produce clearance; citation concentration cannot imply a proven ring; conservative fact-check interpretation | In progress: source and researcher evidence abstention, incoming-only concentration without ring penalties, honest reports/results/history and public copy corrections verified. Legacy-result treatment, explicit outcomes across remaining steps and full claim/entitlement audit remain open. |
| M2: Dependable execution | Worker owns execution; atomic claims, retry/recovery; shared durable files; bounded safe outbound requests | In progress: PostgreSQL execution/migration and killed-worker recovery verified; browser progress, disconnect fallback and result refresh verified with controlled pipelines. Private artifact storage, resumable migration and bounded fetching implemented. Real Redis delivery, live object storage, production egress and host restart acceptance remain open. |
| M3: Reference evidence | PDF/text reference inventory, metadata matching, explicit unknowns, evidence snapshots | Open; requires representative labeled corpus and agreed quality targets |
| M4: Review workflow | Assignments, dispositions, history, versioned exports, privacy/retention | Open; verify completed review and retrievable evidence with pilot users |
| M5: Paid pilot and operations | Entitlements/metering, session lifecycle, recovery drills, operating metrics and partner validation | Open; requires external operational and customer evidence |

## Implementation log

### 2026-10-31: Fact-check fallback correctness

- Replaced substring rating classification with explicit normalized labels.
  `incorrect`, `inaccurate` and `not true` map to false; unknown labels abstain.
- All returned reviews participate in the fallback: conflicting or unsupported
  labels produce unverified with zero confidence instead of selecting the first.
- Added regression cases for negative, partial, unknown and conflicting ratings,
  including order independence and preservation of review sources.
- Malformed model JSON shapes, non-finite/invalid confidence values and invalid
  verdict types now abstain rather than crashing the verification step.
- Python 3.12.10 is installed under the user's local Programs/Python directory.
  WinGet and curl downloads were replaced after verified transfer failures;
  aria2 completed the official installer. SHA-256 matched WinGet's checksum and
  Authenticode identified the Python Software Foundation with a valid signature.
  Installer exited 0. Backend dependencies installed in `backend/.venv`;
  `python -m pip check` reports no broken requirements. Setup processes finished.
- Limitation: search returns similar claims; exact claim matching and verified
  supporting passages are still required. This change does not complete grounded
  fact verification or the broader honest-results milestone.

### 2026-10-31: Honest inputs, results and public scope

- Failed URL/PDF extraction no longer analyzes a URL or filename as source text.
  Failure persists unavailable assessments, terminal time and structured coverage
  warnings. Regression cases cover unavailable/empty URL content, missing PDF
  path and PDF extraction exceptions; these cases pass in the backend suite.
- Shared and private result views show unavailable score and unassessed AI/claims
  explicitly. A failed run no longer displays an active spinner. Component
  regression passes for both access modes.
- Pricing quotas match `backend/app/constants.py`: Free 10/5/5 and Pro 100/50/50
  source checks/researcher analyses/reports monthly. Pro registration is described
  as interest rather than paid activation. Unavailable institution features are
  marked planned; unsupported accuracy and automatic content-discard promises
  are removed.
- Replaced unsupported competitor benchmark/pricing comparisons with current
  capability/limitation scope. Hero, feature descriptions, metadata, footer and
  welcome tour now distinguish source checks from researcher lookups, identify
  illustrative examples and avoid promises of plagiarism/ring proof. Tour version
  bumped so returning users receive the corrected explanation.
- Verification: frontend `npm ci` completed, `npx tsc --noEmit` passed, ESLint
  passed for all changed frontend files, and all 35 frontend unit tests passed.
- Remaining: researcher scoring still needs no-evidence abstention and citation
  concentration must stop producing ring penalties. Existing stored results have
  not been migrated. Landing illustrations and other product surfaces still need
  a full claims review. These fixes do not establish production readiness.

### 2026-10-31: Source evidence abstention and report preservation

- Source formula 1.1 withholds credibility when no positively confident known
  claim verdict exists or a required input/verification step failed. Empty
  evidence has zero score confidence; missing AI or claim assessment remains null.
  Completion of job execution is separate from availability of its assessment.
- Persisted score breakdowns include assessment status and a missing-evidence
  warning; coverage communicates why the headline is unavailable. Individual
  findings remain available. Researcher formula stays at 1.0 pending its own fix.
- Shared/private full-width, PDF and comparison views preserve null scores.
  Report loaders, full/executive/comparison templates and narrative generation
  preserve unavailable assessments rather than inventing zero or clearance.
- Scheduled summary averages exclude unavailable assessments and non-completed
  jobs, retain genuine zeroes, and describe their latest-20 completed-check sample.
- Added scoring, pipeline-persistence, report-loading/rendering/narrative and
  summary regressions. Python syntax compilation and frontend type/lint/unit
  checks passed; backend regressions and full unit suite passed (details below).
- Remaining limits: source scoring still combines authorship style with accuracy;
  individual claim source grounding is not validated; partial coverage is not
  yet a complete explicit step-outcome model. Historical scores are unchanged.

### Tooling

- Installed official `openai/skills` curated `security-best-practices` and
  `playwright` skills using the skill installer. Catalog listing returned HTTP
  403; installation from the known repository paths succeeded. Skills become
  available on the next turn.
- Connected MCP tooling was inspected. Current implementation and checks use
  repository/runtime tools; no additional MCP server was necessary or installed.

### Earlier source-verification checkpoint

- `backend/.venv/Scripts/python.exe -m pytest -q`: **464 passed, 1 deselected**
  in 24.71 seconds. The integration marker is excluded by repository default;
  this is not evidence of real PostgreSQL/Redis/worker or deployment behavior.
- Focused scoring/pipeline/report/governance run: **117 passed**. Report
  availability suite rechecked after final template formatting: **7 passed**.
- Frontend `npm run test:unit`: **35 passed**; `npx tsc --noEmit` and ESLint
  for all changed frontend files passed. `git diff --check` passed.
- Python compile checks and `pip check` passed. Existing backend warnings
  remain for deprecated `utcnow` and an unrelated async test double; frontend
  runtime reports Node deprecation/experimental-storage warnings.
- The first full backend run exposed unit route fixtures contacting a real
  Celery broker. That run was stopped; source/researcher fixture submissions
  now use mocks, and the researcher rerun asserts the expected job dispatch.
  The subsequent full run completed successfully.
- No database migration, real provider call, browser smoke suite, deployed
  rollout, stored-result backfill or customer validation has been performed.

### 2026-10-31: Researcher evidence and revision integrity

- Citation lookups distinguish successful empty pages from unavailable provider
  responses. Graphs track attempted/successful paper lookups, failures, missing
  identities, sample limits and citing-paper/cited-paper/author identifiers.
  Duplicate paper relationships and repeated authors no longer inflate counts.
- Incoming-only clusters remain exploratory citation concentration. New analyses
  emit empty legacy ring/pair arrays, retain observed paper relationships, remove
  unsupported ring/pair score penalties and stop subtracting frequent citers from
  citation counts or marking their citations suspicious.
- Researcher formula 1.1 withholds scores, adjusted metrics and self-citation
  rates for missing/partial citation evidence, zero checked citations, required
  analysis failures or official citation counts conflicting with the sample.
  A missing journal-topic result is surfaced when eligible papers were unassessed.
  Available estimates explicitly describe their sampling and heuristic limits.
- Collector and analyzer failures clear stale assessments. The worker reports
  actual terminal failure instead of always returning completed. Worker and SSE
  paths capture prior metrics before the separate collection phase changes them;
  unavailable prior revisions are also snapshotted and publication rows replaced.
  Reported failure events are persisted before SSE disconnect checks.
- Detail and comparison views preserve unknown scores, explain coverage, and link
  concentration observations to both papers. Missing evidence is not displayed as
  zero or “no flags.” High-score explanations describe heuristic deductions,
  without declaring a researcher exemplary or cleared. Real numeric zeroes remain
  distinguishable from unavailable values.
- Snapshot responses expose formula versions. Watchlist deltas require matching
  known methods; history avoids plotting incompatible/unknown versions as one
  trend and uses the prior analysis capture date when available.
- Researcher reports and institutional summaries preserve unknown assessments.
  Full reports include coverage and paper identifiers/links. Narrative generation
  abstains on unavailable evidence; prompts for available samples avoid treating
  concentration as a ring or the heuristic as a validated integrity probability.

### Researcher verification checkpoint

- Full backend unit suite: **508 passed, 1 integration test deselected** in
  28.16 seconds. Includes provider outage/empty-page distinctions, partial author
  coverage, duplicate citation rows, the reproduced one-way star graph, failed
  analyzer steps, stale-result clearing, cross-method deltas, and worker/SSE
  collection-to-analysis revision boundaries. Database and provider dependencies
  are stubbed; these are not distributed execution or live-provider tests.
- Frontend unit suite: **43 passed**. TypeScript and ESLint on changed researcher
  views, shared components, explanations and API types passed. `git diff --check`
  passed (Git only notes configured LF-to-CRLF conversion).
- Playwright CLI with headless Chromium verified the actual Next.js detail view
  at desktop and 390x844 mobile widths, and the mobile comparison view. Synthetic
  local auth and browser-intercepted API fixtures supplied unavailable results.
  Verified no score meters for unknown values, visible lookup coverage and paper
  links, two unavailable comparison cards, no misleading “No flags raised” empty
  state, and no horizontal page overflow. Console errors: **0**.
- Browser artifacts under ignored `output/playwright/`: screenshots
  `researcher-unavailable-desktop.png`, `researcher-unavailable-mobile.png`,
  `researcher-compare-unavailable-mobile.png`, plus local fixture/state scripts.
  The dedicated browser and local dev server were closed after verification.
- Generated `researcher-unavailable-report.pdf` using the real PDF conversion
  function. Extracted PDF text preserves “Unavailable,” “Not assessed,” coverage,
  and citing/cited paper identifiers. Renderer: **pymupdf-fallback**, one page;
  evidence saved in `researcher-report-check.json`. Native GTK/Pango is unavailable
  here, so styled WeasyPrint output is not verified.
- Local Next.js used fallback fonts after Google Fonts requests failed, and its
  report-only CSP logged local HTTP API connections. Responsive/semantic checks
  passed under those conditions; this is not a production visual or CSP audit.
- Remaining: historical stored scores/ring labels have not been recomputed or
  backfilled; legacy coverage warnings and method versioning make that limitation
  explicit. Heuristic thresholds/confidence are not validated against a labeled
  corpus. The collector and analyzer still fetch through overlapping paths, and
  worker/SSE execution still needs atomic ownership and durable recovery in M2.

## Next work

1. Finish the public/product claims audit, including source score explanations,
   methodology/demo surfaces, legacy results and entitlement source-of-truth design.
2. Extend explicit partial/failed/unsupported outcomes across remaining steps;
   source formula 1.2 now separates authorship style from accuracy scoring.
3. Implement M2's worker ownership, recovery, shared storage and outbound request
   restrictions; reconcile the overlapping researcher collection paths.
4. Build the reference-review inventory/evaluation and professional review loop
   in M3/M4, with pilot and operational evidence for M5.


### 2026-10-31: Source formula 1.2 and durable execution foundation

- Source formula **1.2** removes AI style, unverified-claim and inaccessible-link
  deductions. Missing verification still abstains. Unknown claims, truncated or
  capped samples and unsupported text/PDF bibliography extraction mark results
  partial. Confidence is labeled an uncalibrated evidence indicator; truncation
  cannot increase it. UI explanations and reports describe sampled findings.
- Fact verification preserves successful claims when another claim or AI style
  service fails. Failed claims persist as unverified, with explicit coverage.
- Migration **0018_analysis_runs** applied successfully after all prior migrations
  to a fresh native PostgreSQL **16.15** database on loopback port 55432. Docker
  cannot run on this host because virtualization/Virtual Machine Platform is
  unavailable. No host feature or firmware settings were changed.
- Source/researcher submissions now atomically persist durable intent. Workers
  claim once, validate ownership at every business commit, persist progress, and
  reject stale owners. Researcher prior revisions survive retries. SSE now only
  replays committed events, with Last-Event-ID support; disconnects do not execute
  or stop the worker. Beat retries delivery and reconciles expired attempts.
- PostgreSQL integration verification: **9 passed, 1 skipped**. The skipped case
  needs real Redis. CI now supplies Redis 7 and runs this suite, including a real
  worker delivery case that does not open SSE or call external providers. This
  CI case has been authored, not observed passing in this workspace.
- Final unit verification: **510 backend tests passed**, 11 integration tests
  deselected by default; **43 frontend tests passed**, TypeScript and changed-file
  ESLint passed. Required backend Ruff error checks and Python compilation passed.
  Ruff found an existing unreachable duplicate block in invite-token decoding;
  removing that dead block resolved its undefined-name errors without changing
  token behavior. `git diff --check` passed.
- New migration downgrade to 0017 and upgrade back to head both passed on the
  isolated integration database. Compose configuration parsing passed with
  service env-file resolution disabled (no root `.env` exists); this does not
  establish container startup or shared-volume runtime behavior.
- Compose shares named upload/report volumes between API and worker. Configuration
  and runtime verification remain distinct: local Docker startup is unavailable.
  Production across separate hosts still needs shared durable object storage.
- [Execution runbook](analysis-execution.md) covers upgrade/drain requirements,
  required beat/worker processes, legacy jobs without runs, and limitations.
  Provider requests/costs can repeat after crashes; exactly-once billing is not
  claimed. No production deployment or historical-result recomputation occurred.

Next M2 checks: real broker/worker and process-kill recovery, resumable browser
behavior against the real API, shared storage across instances/restarts, outbound
request restrictions, and reconciliation of overlapping researcher collectors.
M1 still needs legacy-result treatment, full public claim/entitlement review and
reference-grounding evaluation. M3-M5 remain open.


### 2026-10-31: Bounded public fetching and isolated PDF assets

- Article scraping and citation HEAD checks now use a dedicated public HTTP
  transport. It rejects credentials, non-HTTP(S) schemes, nonstandard ports,
  private/reserved/multicast/transition addresses, and mixed public/private DNS
  answers. Connections use the validated numeric address while preserving the
  original HTTP Host and TLS server name. Environment proxies are disabled.
- Every redirect is revalidated, with at most five hops. Fetches have a 20-second
  total deadline, bounded DNS/connect/read times, and a 2 MiB streamed-body limit.
  Compressed bodies are rejected before decompression; article fetching accepts
  HTML/XHTML/plain text. Relative references use the final redirected article URL.
- Report logos are fetched through the same transport, limited to PNG/JPEG and
  four million pixels, then decoded, resized and embedded as PNG pixels. Both
  manual and scheduled report paths use this preparation. Failed logos retain
  organization name/color branding. PDF rendering rejects external network URLs,
  filesystem URLs, fonts, SVG and arbitrary data URIs.
- Dependencies explicitly include httpcore's public network-backend API and
  Pillow for raster sanitization. `pip check` passed. Implementation follows the
  HTTPX transport and HTTPCore network-backend interfaces; protocol tests verify
  numeric connection targets, original TLS identity and resource closure.
- Final backend suite: **555 passed, 11 integration tests deselected**. Required
  Ruff error checks passed. Tests cover malicious URL forms, DNS answers,
  redirect destinations, environment proxies, size/deadline limits, compressed
  bodies, final-location references, invalid/excessive logos and renderer fetch
  restrictions. These are controlled protocol/fixture tests, not a live egress
  or production PDF-renderer audit. Existing 21 test warnings remain.
- Real Redis/worker delivery, process-kill recovery, shared storage across hosts,
  legacy results, provider grounding and M3-M5 are still open. The active goal
  is not complete; no production deployment occurred.

### 2026-11-01: Shared PDF artifact storage

- New uploaded, annotated and report PDFs use opaque artifact references through
  one shared storage interface. API uploads/downloads, worker extraction and
  annotation, manual/scheduled reports, cache invalidation and orphan cleanup
  use it. Existing ownership/share checks still precede artifact reads.
- Added atomic local and private S3-compatible backends. Compose shares
  `/app/artifacts` between API and worker. S3 uses a configured bucket/prefix and
  SDK credential chain with bounded timeouts/retries. No cloud bucket was created
  and no public ACL is requested. Legacy paths require trusted storage roots.
- Orphan discovery paginates beyond referenced objects and caps deletion at
  1,000 candidates per sweep, protecting live and recoverable DB references.
- Full backend check: **567 passed, 11 integration tests deselected** before the
  final pagination regression. Storage suite after that addition: **13 passed**,
  including separate-process reads, PDF extraction/annotation, download ownership,
  atomic failure and S3 SDK contracts. The opt-in live S3 test skipped because
  no dedicated bucket was configured. Ruff, pip dependency, Compose configuration
  and diff checks passed.
- Official Windows MinIO current/archive downloads returned HTTP 410. No native
  object server was started. Stubbed SDK tests do not establish live provider or
  cross-host/restart behavior; those acceptance gates remain open.
- [Storage guide](artifact-storage.md) documents setup and legacy migration.
  An automated migration utility remains pending before switching an existing
  installation. No historical paths were rewritten or production deployment made.

### 2026-11-01: Verified, resumable artifact migration

- Added `python -m app.cli.migrate_artifacts`. Default mode inventories source
  PDFs and writes a reviewable manifest without copying objects or changing DB
  references. Initial manifest creation cannot overwrite another plan. Apply
  requires explicit maintenance confirmation and refuses queued/running jobs.
- Source/destination stores are independently configurable. Copies are verified
  by SHA-256 and journaled before DB updates. Each shared-reference group moves
  transactionally, including cloned sources and soft-deleted records. Changed
  source files or DB references fail safely; a final inventory detects unplanned
  reference changes. Source copies remain intact.
- A dedicated PostgreSQL connection holds an advisory lock across group commits,
  preventing a second migrator. Reapplying the same manifest verifies and reuses
  copied objects rather than duplicating them. Destination config must match the
  reviewed plan. Added a timed orphan-cleanup hold for the rollback window.
- PostgreSQL acceptance: **7 passed**, including a child process abruptly exiting
  after copy journaling, then successfully resuming with the same destination
  object and released advisory lock. Also covers dry-run immutability, source and
  destination hash failures, alias rollback, active work and concurrent migration.
  Source/target stores in these tests are isolated local directories; this is not
  live S3 or analysis-worker crash acceptance.
- Expanded CI's PostgreSQL integration step to run migration acceptance tests.
  Final backend suite: **572 passed, 19 integration tests deselected**; Ruff,
  dependency and diff checks passed. Windows pytest shutdown reported a temp
  directory permission error after the passing run; test exit status was zero.
  The existing 21 test warnings remain.
  [Storage guide](artifact-storage.md) now includes plan/apply/resume commands,
  maintenance requirements, backup/rollback handling and cleanup preservation.
  No production migration, historical-path rewrite or deployment was performed.

### 2026-11-01: Killed-worker recovery and functioning progress messages

- Added real child-process kill tests around durable coordinator execution.
  Killing a source worker before result commit queues one replacement; killing
  it after result commit finalizes without recomputing. Each path leaves one
  finding and one terminal event. Killing a researcher worker during metric
  collection or after a failed-result commit preserves the original revision
  once and clears stale current assessments.
- Tests forcibly terminate processes, accelerate lease expiry in PostgreSQL and
  recover through production claim/reconciliation/fencing code. Pipeline fixtures
  make no provider requests. They prove those checkpoint boundaries, not Redis
  redelivery, real provider requests, or complete host-restart behavior.
- Found and fixed an actual progress protocol mismatch: both submission screens
  listen via EventSource.onmessage, while named backend events bypassed those
  handlers. Streams now send standard `message` events with step names in JSON.
  Real source/researcher HTTP route tests verify tickets, serialized wire format,
  completed-run replay, Last-Event-ID, invalid cursors and zero execution attempts
  caused by streaming. Browser UI acceptance remains pending.
- Final verification: **572 backend unit tests passed**, 25 integration tests
  excluded by default. Combined PostgreSQL execution/migration suite: **22 passed,
  1 skipped**; only real Redis delivery skipped in that suite. Ruff and diff checks
  passed. Existing test warnings and Windows shutdown temp-cleanup permission
  logging remain; test processes exited successfully.
- [Execution guide](analysis-execution.md) distinguishes proven kill recovery from
  outstanding real broker, host restart, browser and live object-store gates.
  M1/M2 remain in progress and M3-M5 open. No production deployment occurred.

### 2026-11-01: Browser progress and recovery acceptance

- Found a second recovery gap: result pages fetched only once, so disconnect
  fallback and researcher reruns could remain stuck on pending/processing.
  Both result pages now refresh every three seconds while active, with serial
  requests, navigation cancellation, transient-error notices and terminal stop.
  Final refresh also retrieves researcher history/graph and PDF positions.
- Submission screens open results on failed terminal events and ticket failures,
  preserving access to already-submitted work instead of returning to an idle
  form with hidden progress. Updated the stale source stream docstring.
- Real Chromium with local API/PostgreSQL verified both live progress screens,
  source completion, researcher failure, premature stream EOF for both kinds,
  completion through result polling, offline/reconnect recovery, an in-place
  researcher rerun to failure and source ticket-503 fallback. Running mobile
  source/researcher pages fit a 390px viewport. Six persisted runs each had one
  attempt and one terminal event; no stream or result read duplicated execution.
- Scope: real routes, JWT ownership, persistence and coordinator; controlled
  pipeline outputs and suppressed broker publication. The ticket-503 case used
  a browser route override. Offline faults produced expected network/NextAuth
  error logs; normal online flows had no console errors. Existing development
  CSP report-only messages remain. This is not live provider/Redis acceptance.
- **49 frontend tests passed**, including six refresh regressions; TypeScript,
  changed-file ESLint and diff checks passed. The prior backend checkpoint
  remains **572 unit / 22 PostgreSQL integration tests passed**, one Redis skip;
  backend behavior was not changed or broadly retested in this checkpoint.
- Real broker delivery, live S3, host restart, legacy-result treatment and M3-M5
  remain open. Changes are uncommitted; no production deployment occurred.
