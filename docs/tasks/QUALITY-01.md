# QUALITY-01: [QUALITY-01] Verify evidence-grounded analysis and assess PR16

Issue: #35

Owned paths: backend/tests/test_pilot_evidence_acceptance.py (new); backend/tests/fixtures/pilot_evidence/ (new); docs/ANALYSIS-ACCEPTANCE.md.

Goal: Current-source audit plus executable offline acceptance probes for unsupported model verdicts, empty sources, contradictory citations, insufficient evidence, researcher identity/ORCID ambiguity, provider routing and report provenance. Historical audit claims are hypotheses: independently reproduce current paths and distinguish concrete bug, source-derived risk and untested provider behavior. Inspect PR16 diff/migrations read-only against current main; do not checkout into another lane or merge/cherry-pick it. Prioritize findings with file:line and minimal reproducer. No service/model/router/migration implementation edits in first slice; manager will assign concrete fixes without overlap. Model fixture output is intentionally synthetic and must be labeled, never live-provider evidence. Run tests; if acceptance fails publish bounded draft with failures rather than weakening assertions. No network scraping/paid-provider calls/customer data.

Branch: agent/quality-01/pilot-readiness
Worktree: D:/Developer/ArtiProof-worktrees/quality-01
Ports: frontend 3205, backend 8205; optional disposable Postgres 55445, Redis 56445; verify ports unused before binding. Only stop processes/resources you create.

## Shared manager contract
Base: e1372a722b2f4e25ff38505238c62b93d0af49ad; manager branch docs are reference, source baseline is main. Read D:/Developer/ArtiProof-worktrees/manager/AGENTS.md and relevant frontend/AGENTS.md, actual manifests and definitions before edits.
You implement through OpenCode; Hermes manages integration and independent review. Read issue/comments and publish milestone handoffs. Exclusive claim lasts this bounded run, maximum90minutes; stop with preserved work and exact handoff when blocked/expired. Do not reassign yourself or restart global services.
No secrets/.env/credential reads; no production/customer data, paid model calls, deployment, merges, direct-main changes, force-push, self-approval or other worktree edits. No root/shared compose invocation, destructive reset/stash, broad installs or shared env mutation. New test-only local credentials are synthetic, not existing credentials.
Use one isolated worktree and own dependency installs; existing scratch venv may be used READ-ONLY, otherwise own scratch venv. No node_modules links to another lane. Use scratch C:/Users/Axel/AppData/Local/hermes/cache/scratch/<lane>/ for artifacts. Never global pip/npm installs. No concurrent build processes inside your own tree.
Change ONLY named owned paths. Inspect symbols before edits. Regression-first for behavior changes. Missing services/fixtures/failed assertions/skips are not passes. No approval for production access implied by this assignment. Commit/tag/push small slices on assigned branch and draft main-target PR, REFERENCES issue without auto-close keywords if broader acceptance incomplete. Use human Git identity Axel, [TAG] subject and Agent-Tag/Device-Tag: axel-windows trailers. Verify pushed SHA and read back remote PR. Full relevant tests/lint/types/build and hosted results as appropriate; bounded CI observation must stay attached, not orphan a watcher then claim completion. No blanket green claim from component CI.
Handoff exact SHA, changed paths, actual commands/results, skips/exclusions, blockers with owner/path, next scope needed. Stop writers after handoff; manager reviews/cherry-picks/merges only exact reviewed green combined trees.
