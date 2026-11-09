# DATA-01: Legacy metadata inventory and reversible remediation design

Issue: #32

Owned paths: docs/LEGACY-DATA-PLAN.md; backend/tools/legacy_data_audit/ (new offline tools only); backend/tests/test_legacy_data_audit.py; backend/tests/fixtures/legacy_data_audit/ (new synthetic fixtures).

Goal: Trace actual migrations/models/consent/report/share provenance. Build an OFFLINE metadata-only classifier taking explicit synthetic JSON input, with no DB connection or production-write mode. Failing regressions for ambiguous provenance, no inference from current organization pointer, no customer text or tokens in output. Propose quarantining/re-consent and explicit reversible mappings rather than silently restamping/deleting. Include required inventory fields, backup/restore prerequisites, dry-run review and manual approval gates. Test synthetic upgrade-shaped cases. Real historical audit remains blocked on separate access approval; do not imply performed. Coordinate with OPS01: you own record remediation logic; OPS owns environment recovery rehearsal.

Branch: agent/data-01/pilot-readiness
Worktree: D:/Developer/ArtiProof-worktrees/data-01
Ports: frontend 3201, backend 8201; optional disposable Postgres 55441, Redis 56441; verify ports unused before binding. Only stop processes/resources you create.

## Shared manager contract
Base: e1372a722b2f4e25ff38505238c62b93d0af49ad; manager branch docs are reference, source baseline is main. Read D:/Developer/ArtiProof-worktrees/manager/AGENTS.md and relevant frontend/AGENTS.md, actual manifests and definitions before edits.
You implement through OpenCode; Hermes manages integration and independent review. Read issue/comments and publish milestone handoffs. Exclusive claim lasts this bounded run, maximum90minutes; stop with preserved work and exact handoff when blocked/expired. Do not reassign yourself or restart global services.
No secrets/.env/credential reads; no production/customer data, paid model calls, deployment, merges, direct-main changes, force-push, self-approval or other worktree edits. No root/shared compose invocation, destructive reset/stash, broad installs or shared env mutation. New test-only local credentials are synthetic, not existing credentials.
Use one isolated worktree and own dependency installs; existing scratch venv may be used READ-ONLY, otherwise own scratch venv. No node_modules links to another lane. Use scratch C:/Users/Axel/AppData/Local/hermes/cache/scratch/<lane>/ for artifacts. Never global pip/npm installs. No concurrent build processes inside your own tree.
Change ONLY named owned paths. Inspect symbols before edits. Regression-first for behavior changes. Missing services/fixtures/failed assertions/skips are not passes. No approval for production access implied by this assignment. Commit/tag/push small slices on assigned branch and draft main-target PR, REFERENCES issue without auto-close keywords if broader acceptance incomplete. Use human Git identity Axel, [TAG] subject and Agent-Tag/Device-Tag: axel-windows trailers. Verify pushed SHA and read back remote PR. Full relevant tests/lint/types/build and hosted results as appropriate; bounded CI observation must stay attached, not orphan a watcher then claim completion. No blanket green claim from component CI.
Handoff exact SHA, changed paths, actual commands/results, skips/exclusions, blockers with owner/path, next scope needed. Stop writers after handoff; manager reviews/cherry-picks/merges only exact reviewed green combined trees.
