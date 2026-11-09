# OPS-01: [OPS-01] Prepare isolated pilot release and recovery rehearsal

Issue: #36

Owned paths: docs/PILOT-RELEASE-RUNBOOK.md; scripts/pilot_rehearsal/ (new); backend/tests/test_pilot_rehearsal_safety.py (new).

Goal: Trace deploy entrypoints, migrations, artifacts, worker scheduling/health and monitoring from repository only. Build offline preflight/checklist and an isolated synthetic backup/restore rehearsal if local tooling permits, no root docker-compose invocation (contains env_file/shared volumes). Use dedicated explicit test-only names/ports, reject non-loopback/live endpoints and unknown databases, never destructive cleanup of preexisting resources. Evidence must separate tested local recovery from proposed hosting commands. Require recoverable DB plus artifact backups, migration-head verification, rollback rehearsal, observability/alerts, cohort limits, support ownership and explicit manual go/no-go. DATA01 owns provenance/remediation; you own environment and recovery. No actual deployment/cloud/production access or migration edits. Stage runbook can list required owner decisions without guessing credentials or live topology.

Branch: agent/ops-01/pilot-readiness
Worktree: D:/Developer/ArtiProof-worktrees/ops-01
Ports: frontend 3206, backend 8206; optional disposable Postgres 55446, Redis 56446; verify ports unused before binding. Only stop processes/resources you create.

## Shared manager contract
Base: e1372a722b2f4e25ff38505238c62b93d0af49ad; manager branch docs are reference, source baseline is main. Read D:/Developer/ArtiProof-worktrees/manager/AGENTS.md and relevant frontend/AGENTS.md, actual manifests and definitions before edits.
You implement through OpenCode; Hermes manages integration and independent review. Read issue/comments and publish milestone handoffs. Exclusive claim lasts this bounded run, maximum90minutes; stop with preserved work and exact handoff when blocked/expired. Do not reassign yourself or restart global services.
No secrets/.env/credential reads; no production/customer data, paid model calls, deployment, merges, direct-main changes, force-push, self-approval or other worktree edits. No root/shared compose invocation, destructive reset/stash, broad installs or shared env mutation. New test-only local credentials are synthetic, not existing credentials.
Use one isolated worktree and own dependency installs; existing scratch venv may be used READ-ONLY, otherwise own scratch venv. No node_modules links to another lane. Use scratch C:/Users/Axel/AppData/Local/hermes/cache/scratch/<lane>/ for artifacts. Never global pip/npm installs. No concurrent build processes inside your own tree.
Change ONLY named owned paths. Inspect symbols before edits. Regression-first for behavior changes. Missing services/fixtures/failed assertions/skips are not passes. No approval for production access implied by this assignment. Commit/tag/push small slices on assigned branch and draft main-target PR, REFERENCES issue without auto-close keywords if broader acceptance incomplete. Use human Git identity Axel, [TAG] subject and Agent-Tag/Device-Tag: axel-windows trailers. Verify pushed SHA and read back remote PR. Full relevant tests/lint/types/build and hosted results as appropriate; bounded CI observation must stay attached, not orphan a watcher then claim completion. No blanket green claim from component CI.
Handoff exact SHA, changed paths, actual commands/results, skips/exclusions, blockers with owner/path, next scope needed. Stop writers after handoff; manager reviews/cherry-picks/merges only exact reviewed green combined trees.
