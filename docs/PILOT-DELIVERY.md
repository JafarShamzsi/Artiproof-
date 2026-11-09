# Pilot delivery board

Assessment baseline: main `f551c5b`. This is a delivery plan, not a production-readiness certificate. GitHub issues and PR comments carry live ownership/status.

## Release sequence

### Owner-confirmed rollout decisions

- The owner confirmed deployment is manual or disabled; merging main is not intended to release automatically. This is owner confirmation, not an inspection of current Railway settings. Independently reviewed, green code may be integrated through the manager; deployment remains a separate approval.
- Retain existing data and audit/remediate it before the pilot. Do not substitute a clean database, discard records, or treat new-code tests as historical cleanup evidence. Inventory uncertain enrollment and resource/report/share provenance, propose quarantine and re-consent, and verify backups and rollback before separately authorized changes. This decision does not authorize reading customer contents or modifying production data.
- Historical-data remediation is therefore a required release gate, not an optional alternative to clean initialization. Keep deployment blocked until the owner approves the evidence-backed remediation and release plan.

1. **Safe development and tenancy:** reproducible CI/build, no forced team enrollment, no personal-history leakage, no secrets in automation.
2. **Trustworthy source review:** honest claim provenance, explicit unknown retraction states, PDF/text coverage parity and usable evidence links.
3. **Bounded assisted pilot:** enforced trial/usage budgets, reliable sessions, controlled sharing/deletion, recoverable separate API/worker/storage deployment.
4. **Useful recurring workflow:** reference extraction evaluated on representative manuscripts; reviewer decisions and versioned exports; real partner feedback.
5. **Public launch:** selected billing provider, durable payment/entitlement reconciliation, operational recovery evidence, dependency/security gates and customer support ownership.

No date commitment until the first real partner workflow and environment are identified. Prefer a small assisted pilot over selling unsupported capabilities.

## Historical first parallel lanes

| Agent tag | Scope | Acceptance |
|---|---|---|
| manager | AGENTS.md, portable task skills, briefs, issue coordination | Another device can pick up a confirmed issue without relying on this conversation |
| ci-01 | CI/workflow tooling only; runtime/build configuration if needed | Real PR checks execute backend unit/integration, frontend lint/types/unit/build/smoke; failures are not hidden |
| security-01 | Team invitation consent and organization-scoped activity | Existing accounts cannot be silently joined; personal/other-org activity never appears in team feed; acceptance/revocation/expiry tested |
| build-01 | Review existing team Suspense fix and two regression tests | Independent review, tests and production webpack build; small isolated PR |

These were the original assignments, not current ownership grants. Current claims supersede them; do not restart historical lanes without manager confirmation.

## Current pilot-readiness lanes

All six current lanes start from reviewed main `e1372a722b2f4e25ff38505238c62b93d0af49ad`. See `docs/tasks/PILOT-LANES.json`, each named brief, and live issue comments for exact writable paths, ports and bounded claims. Local paths are host-specific examples, not cross-device requirements.

| Agent | Issue | Exclusive responsibility |
|---|---|---|
| DATA-01 | #32 | Offline synthetic legacy metadata classification and remediation design; no live data access |
| DEPENDENCIES-01 | #26 | Package manifests/lockfile, queue compatibility and dependency audit |
| QA-01 | #34 | Separate authenticated test harness and synthetic fixtures; no application fixes |
| UX-01 | #33 | Mobile measurements and narrowly assigned cookie/comparison components |
| QUALITY-01 | #35 | Evidence acceptance probes and read-only PR #16 assessment |
| OPS-01 | #36 | Offline release preflight, synthetic recovery rehearsal and runbook |

The manager owns CI, shared instructions, cross-lane API/schema decisions and integration. DEPENDENCIES-01 alone owns current manifest changes. Other agents report out-of-scope defects for explicit reassignment instead of editing shared files. Each claim expires with its bounded run (maximum 90 minutes); no automatic takeover. Proposed tools or passing synthetic tests do not authorize production access or deployment.

## Prioritized backlog

Items below are audit findings to reproduce against the latest merged code, not a claim of live exploitation. Resolve existing PR overlap before assigning implementation; issue acceptance and executable tests determine closure.

### Block pilot

- **P0 Tenant consent/privacy:** organizations.py attaches existing accounts immediately; analytics.py scopes recent resources to member user IDs instead of resource organization. Reproduce via tests, implement explicit acceptance and strict activity boundaries. Audit existing memberships before production rollout; code fix does not repair historical disclosures.
- **P1 Evidence provenance:** fact_checker.py accepts model-only verdicts with empty sources; positive confidence can unlock a headline score. Abstain without retrieved, matched support. A generated URL is not grounding.
- **P1 Retraction unknowns:** provider failures collapse to false; report labels can become OK. Introduce checked/unknown/unavailable semantics throughout API/UI/export.
- **P1 Trial and metering:** team creation grants unlimited tier, expiry is not evaluated in quota enforcement, deletion reduces counted usage, scheduled reports bypass quotas. Effective entitlement resolver and deletion-independent consumption/reservations; bounded pilot budgets.
- **P1 Sessions:** connect refresh and logout revocation to frontend; preserve safe return navigation.
- **P1 Privacy lifecycle:** deletion must account for cached/public derived reports and account records; Google-only users need supported reauthentication. Define and test retention, rather than claiming compliance from soft deletion.
- **P1 Deployment proof:** separate API/worker + real Redis + private shared object storage; restart/retry/replay and restore drill. Existing local fixture evidence is not live-provider acceptance.
- **P1 Usable failure UI:** normalize structured quota/validation errors; never render error objects as React children.

### Build the useful pilot workflow

- Show finding sources and explicit no-evidence state in both PDF and text layouts and exports.
- Share lifecycle/coverage headers across PDF and URL/text results.
- Confirm researcher identity; preserve provider IDs instead of resolving the first name match twice.
- Remove Gemini-specific eligibility/provenance when an alternate provider is selected.
- Extract and resolve PDF/text bibliographies; evaluate ambiguous/unresolved references on a labeled corpus.
- Persist human finding dispositions separately from machine output and bind reports to reviewed revisions.
- Fix Team CTA destination and preserve trial intent through auth.
- Make scheduled reports claim-based/idempotent and separate singleton beat before scaling workers.

## Existing work to reconcile

PR #16 (`feat/roadmap-stages`) contains evidence, multilingual and deterministic-engine work based on older code. Do not merge wholesale or duplicate it blindly. Review current diff, migration lineage (it adds a separate 0018), conflicts with current abstention/storage/run hardening and tests. Salvage independently verified slices. Dependabot PRs need compatibility/security triage, not batch approval.

## Historical initial verification baseline

- Backend: 572 passed, 25 integration tests deselected on Windows/Python 3.14 in an isolated scratch virtualenv. Deprecation and one async-test-double warning remain.
- Frontend before fix: 49 tests, TypeScript, ESLint passed.
- Team fix: regression observed failing first; 51 tests, lint and webpack production build pass after fix.
- Default Turbopack initially failed in Google Fraunces font resolution; BUILD-01 later reported a successful default build after the team fix. Treat the font failure as intermittent, not an established persistent blocker. CI selects webpack explicitly; neither local run proves every platform.
- Remote main CI failed at Playwright installation on ubuntu-26.04; CodeQL upload failed because code scanning is not enabled. These are remote run findings, separate from local passing suites.
- No real customer, provider, restore, payment or production-security acceptance performed.

## Tool policy and portability

Use the already authenticated OpenCode CLI as implementation harness. Hermes manages and reviews. The initial batch used three bounded worker lanes; the current six assignments are listed above. Keep concurrency bounded by disjoint file ownership and isolated resources; serialize shared schemas/manifests and integration. Each device authenticates itself; never copy OAuth files or secrets between devices.

Portable repo skill: `.agents/skills/artiproof-delivery/SKILL.md`. Native tools already cover filesystem, shell and GitHub; no redundant privileged MCP is required. Browser testing uses pinned Playwright. A browser MCP is optional for exploratory QA, separate from deterministic tests, and must use synthetic data and an isolated browser profile. Do not automatically add cloud/database MCPs or hosted code-indexing services.
