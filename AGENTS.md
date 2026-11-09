# ArtiProof agent delivery contract

## Product and authority

Deliver a supervised research-integrity pilot before a public self-service launch. Preserve uncertainty; model output is not verified evidence and citation concentration is not proof of misconduct. Read PRODUCT.md and docs/product-milestones.md, but verify historical claims against current code.

The project manager scopes work, assigns lanes, reviews evidence and merges. Implementation agents change code only inside their approved task. Agents must not deploy, merge, weaken required checks, change repository visibility, purchase services, or access production data without separate authorization.

## Cross-device coordination

- GitHub issues/PRs are the shared task record; local chat and agent memory are not authoritative.
- Read the issue, all comments, linked PRs and current origin/main before starting.
- Request a manager-confirmed claim containing issue, agent tag, device tag, branch, base SHA, owned paths, expiry and acceptance criteria. An issue comment alone is not an atomic lock. Do not start competing claims until the manager resolves ownership.
- Use one worktree or clone and one branch per task: `agent/<agent-tag>/<short-task>`. Never edit the shared main checkout in parallel.
- Heartbeat on meaningful milestones; stale claims require explicit reassignment. Do not automatically reclaim work after a timeout.
- Different agents may read everything non-secret but must not edit another lane's files. Shared schema, lockfiles, CI and API contracts need explicit ownership or sequencing.
- Before changing schema, inspect all migration heads and open migration PRs. Never duplicate revision identifiers or rewrite released migrations.
- Push only the assigned branch; never force-push, commit credentials, spoof authors, or push directly to main. Stage named files, not unrelated changes.
- Keep the human-authorized Git identity; do not invent agent emails or coauthors. Every commit subject includes `[AGENT-TAG]`, with `Agent-Tag: AGENT-TAG` and `Device-Tag: device-tag` trailers. PR titles, issue handoffs and review comments carry the same unique tag. Tags identify work, not authenticated principals.

## Implement and verify

1. Inspect definitions, callers, local instructions and manifests before editing. Frontend/AGENTS.md takes precedence for Next.js conventions.
2. Reproduce defects and write a failing regression before fixing. Keep changes scoped; no unrelated refactors.
3. Run relevant tests, full affected unit suite, lint/type checks and production build when frontend changes. Database/security work needs real PostgreSQL integration evidence; stub tests alone do not establish isolation.
4. Use dedicated test databases/queues/object prefixes. Never read `.env`, credential stores or live customer records. Never silently use SQLite for PostgreSQL-specific behavior.
5. Distinguish unit, fixture integration, browser, real-provider and deployment evidence. Skips, unavailable tools and existing failures must be reported, never called passing.
6. Open a draft PR linked to the issue. Include agent/device tags, exact head/base SHA, commands/results, unverified acceptance, risk and rollback.
7. Independent reviewer examines the exact head SHA; any new commit invalidates that review. Manager verifies remote checks and merge state.

## Merge and handoff

- Require current backend/frontend CI checks and an explicit independent review record before manager merge. Do not bypass failing gates.
- One shared GitHub login cannot provide genuine independent-account approval. Agent review comments are evidence, not a second authenticated principal. Add a separate reviewer account or restricted GitHub App before enforcing that requirement.
- Prefer small squash-merged PRs; update from main and rerun checks before integration. Never destroy another agent's work to resolve conflicts.
- Handoff: issue/PR, branch and SHA, changed paths, tests, outstanding risks, next dependency. Close issues only after acceptance is verified.

## Tooling

Use git and gh for local/remote state; pytest/Alembic for backend; npm lockfile, Vitest, TypeScript, ESLint and Playwright for frontend. Load the repository skills in `.agents/skills` when applicable. Check installed CLI help rather than assuming agent-harness versions. External MCPs need a concrete purpose, pinned reviewed package, isolated context, no secrets and verified connection; do not install broad filesystem/database/cloud access by default.
