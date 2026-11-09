---
name: artiproof-delivery
description: Use when implementing or reviewing an ArtiProof task.
---

# ArtiProof delivery

Read root AGENTS.md, the assigned GitHub issue and its comments, then instructions in the affected subtree. Read docs/PILOT-DELIVERY.md for dependencies, not live status.

## Preflight

Run `git status --short`, `git branch --show-current`, `git fetch origin`, and inspect the assigned issue/PR with gh. Do not read credentials or .env. Confirm manager-assigned issue, agent/device tag, unique branch, allowed files, base SHA and claim expiry. Stop on overlapping ownership or unknown local changes. Work in a dedicated clone/worktree, never a shared main directory.

## Verification commands

Read manifests and CI first; commands can evolve. Backend: from backend, use an isolated environment with requirements.txt and requirements-dev.txt, run `python -m pytest -q`; run named integration tests only against dedicated migrated PostgreSQL/Redis. Default pytest excludes integration; report that explicitly. Frontend: from frontend, `npm ci`, `npm run test:unit`, `npx tsc --noEmit`, `npm run lint`, `npm run build`, and Playwright acceptance appropriate to the task. Do not replace a failed production build with a passing type check.

For security fixes, prove denial and allowed cases: other user/org, personal data, revoked/expired tokens, replay and concurrency. For findings, distinguish absent evidence from a clean result and test reports/public links as well as private UI.

## Red-green-review

Write a failing regression, observe the intended failure, apply the smallest change and run affected/full checks. Do not disable checks to obtain green. Read sibling call paths for the same flaw. Record environmental blockers exactly.

Commit only approved paths to the assigned branch. Use `Agent-Tag: <tag>` and `Task: #<issue>` trailers; these do not create an authenticated identity. Push the task branch and open a draft PR with acceptance results, exact SHA, risk and rollback. Never merge yourself. A separate reviewer checks the exact head; manager verifies remote CI and integration. Never claim a merge or passing CI from local tests.

## Cross-device handoff

Post a concise issue heartbeat when a milestone finishes or work blocks: branch, SHA, current scope, checks, next action. Finish with a PR link and remaining failures. A new device reads GitHub and fetches the branch; it does not need private chat history. Manager confirms reassignment before work resumes.

## OpenCode on this Windows host

Use native forward-slash paths. Git Bash PWD may be /d/... even when the executable needs D:/...; verified invocation is `PWD='D:/Developer/ArtiProof-worktrees/<lane>' opencode run ...`. Verify installed `opencode run --help`; do not copy flags from a different version. Non-interactive run needs no PTY. Use explicit model and session title, scoped attached brief, and no global auto-approval. Never resume an unrelated user's session.
