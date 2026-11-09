# Overnight 2026-05-30 — what shipped

A run-down of the work landed between you stepping away and morning, for review at coffee.

## TL;DR

- Phase E completed (Observability + Vitest scaffold + Celery DLQ + Gemini cost tracking).
- 20 bugs surfaced by an adversarial multi-agent code review; 14 confirmed and fixed.
- Two new public marketing surfaces shipped (`/demo`, `/methodology`).
- All gates green: 381 pytest pass, 20 vitest pass, 11 Playwright pass, tsc + lint 0/0.
- 8 commits on `main`, local only — nothing pushed to remote.

Read order if you only have 10 minutes: this doc → `git log --oneline main~10..main` → spot-check the diff for the security fix (`backend/app/routers/reports.py`).

## Commits (newest first)

```
eedcef1 fix: watchlist auth + PastAnalyses error surfacing
19289f0 fix: 14 confirmed bugs from overnight adversarial review
0075662 ux: stronger empty states on /reports and /check
a928719 ux: skeleton loaders + recoverable error states on result pages
e36f49a feat(landing): public /demo page + nav/hero CTAs
73ee0a6 Phase E frontend: Vitest scaffold + admin telemetry UI
5524b3a Phase E backend: OTel + Gemini cost tracking + Celery DLQ
c513ca7 Phases 0-D: hygiene + reliability + governance + team-tier + billing scaffold
```

## What changed by area

### Backend

**Phase E telemetry (5524b3a)**

- Migration 0015: `gemini_metrics` + `celery_run_log` + `celery_dlq`.
- New `app/services/gemini/client.py` — every engine now goes through one `call_gemini(prompt, operation=...)` chokepoint that captures `usage_metadata`, records latency, emits an OTel span when a tracer is set, and persists a metric row best-effort. Six engines updated: `claim_extractor`, `fact_checker`, `ai_detector`, `topic_analyzer`, `origin_tracer`, `narrative_generator`.
- New `app/observability/otel.py` — `init_otel(app)` wires FastAPI + SQLAlchemy + Celery auto-instrumentation, gated on `OTEL_EXPORTER_OTLP_ENDPOINT`. No-op when the env var is empty.
- New `app/tasks/observability.py` — `task_prerun/postrun/failure` signal handlers writing to `celery_run_log` and `celery_dlq` via a synchronous psycopg2 session (worker has no asyncio loop in signal context).
- New `app/context.py` — ContextVars for `current_user_id`, `current_source_check_id`, `current_researcher_profile_id`. Orchestrators stash these so the Gemini client attributes rows without plumbing through every helper.
- Admin endpoints: `/api/admin/gemini/cost-summary?days=N`, `/api/admin/celery/runs`, `/api/admin/celery/dlq`, `POST /api/admin/celery/dlq/{id}/retry`.

**Bug fixes (19289f0, eedcef1)**

- `reports.py` /generate: 4 SELECT branches now filter `deleted_at.is_(None)`, preventing a fresh share-link from resurrecting soft-deleted content. **This was the highest-severity finding from the audit.**
- `reports.py` comparison/audit de-dup the id list first; `[a,a,a]` no longer satisfies the "all ids exist" check.
- `billing_webhook.py` no-user path now rolls back and returns 202 deferred instead of committing the orphan event row. The old behavior caused the unique `(processor, processor_event_id)` constraint to permanently swallow upgrades when the signup-webhook race lost to user-row creation.
- `source_check.py` bulk pre-validates every item before creating any rows. Old loop leaked N-1 partial rows on a bad item N.
- `researcher.py` watchlist GET now applies `is_owner_or_org_admin` in Python. The two endpoints had divergent auth — org admins could ADD a teammate's researcher but never see it back through LIST.

### Frontend

**Phase E (73ee0a6)**

- Vitest scaffold: `vitest.config.ts`, `vitest.setup.ts` (jsdom env, RTL matchers, `next/navigation` + `next-auth/react` mocks, localStorage polyfill).
- 10 smoke tests across `apiFetch`, `use-debounced-value`, `cookie-banner`.
- CI job extended with a `npm run test:unit` step between ESLint and Playwright.
- Admin Operations surface bound to the new backend endpoints: Gemini spend card (last 30d total cost + by-operation rollup + top-5 users), Celery DLQ with per-row Retry button.

**Marketing (e36f49a, manual)**

- New `/demo` route — a fully-rendered FullWidthView with hand-curated sample data. Visitors can see exactly what a report looks like without signing up or spending a Gemini quota slot on an anonymous run. Linked from the hero CTA and navbar.
- New `/methodology` route — institutional buyers' #1 procurement question ("how does this actually work, and where does it fail?") answered. Names every engine, its data sources, its weight in the score, and its known limits. Includes the verbatim credibility formula so reviewers can audit deductions.
- Sitemap updated with both routes at priority 0.8-0.9.

**UX polish (a928719, 0075662)**

- `/check/[id]` and `/researcher/[id]` loading states swapped from a centered spinner to a skeleton mirroring the result-page layout.
- Both pages get recoverable error states with Try-Again + Browse-back buttons instead of a flat "not found" sentence.
- `/reports` empty state: dual CTA (Run a source check / Analyze a researcher) with explanatory copy.
- `/check` PastChecks empty state: action link to `/demo` so first-time users can preview before spending their first quota slot.

**Bug fixes from the audit (19289f0, eedcef1)**

- `check/[id]/page.tsx`: state reset on `id` change + cancelled flag — navigating between source checks no longer flashes the previous result.
- `researcher/[id]/page.tsx`: parallel fetch wrapped in try/catch/finally so a network blip can't strand the page on an infinite spinner.
- `researcher/[id]/page.tsx`: header flexes to column at <sm so the 5-button action cluster wraps under the title at 375px.
- `check/page.tsx`: TabsList wrapped in `overflow-x-auto` with `whitespace-nowrap` triggers — 4 tabs scroll on narrow viewports.
- `check/page.tsx`: SSE `onerror` distinguishes clean stream-end (CLOSED) from real connection drop. Real drops toast the user instead of silently rerouting.
- `layout.tsx`: Account dropdown uses `DropdownMenuItem render={<Link/>}` instead of nesting Link inside MenuItem — fixes nested interactive role + keyboard activation a11y bugs.
- `HeroSection.tsx`: secondary CTA gets a focus-visible ring; was stripping the outline with no replacement.
- `cookie-banner.tsx`: focus moves into the banner on first appearance and into the Customise panel heading on expand. Accept-all has a focus-visible ring.
- `FullWidthView.tsx`: badge text shades deepened to -800/-300 pair for AA contrast over /20 tints (both light and dark mode); citation URL ellipsis only appended when truncation actually happened.
- `Navbar.tsx`, `Footer.tsx`, `PricingSection.tsx`: real Next routes use `<Link>`; hash-only and `mailto:` stay `<a>`. Marketing footer clicks no longer trigger full reloads.
- `researcher/page.tsx`: PastAnalyses surfaces fetch failures with Retry instead of empty-state.

## Test counts (before → after tonight)

| Suite | Before | After | Notes |
|---|---|---|---|
| Backend pytest | 372 | **381** | +9 telemetry tests in `test_phase_e_telemetry.py` |
| Frontend vitest | 0 | **20** | scaffolded from zero |
| Frontend Playwright | 11 | **11** | unchanged; covers the existing smoke flows |
| ESLint | 0 errors / 2 warnings | **0 / 0** | cleared the unused-import warnings |
| `tsc --noEmit` | clean | **clean** | unchanged |

## Deferred to follow-up

- **Phase A.5 settings code-split**: deferred per the plan's explicit note. The 2,910-line `settings/page.tsx` is risky to rewrite without a phase-C/D pass touching it; the file shrinks naturally when those phases land.
- **Dashboard range refetch perf** (`dashboard/page.tsx:229`): LOW priority bug-hunt finding. Range change refetches 8 endpoints; should refetch only `/trends`. Touching a 700-line file at 4am is the wrong tradeoff — punted.
- **The 3 remaining bug-hunt items not in this batch** (range refetch, the LOW <a>-vs-Link items that didn't make it, the cookie-banner dialog primitive swap). All LOW severity and tracked in the workflow output if needed.

## Verification commands the morning-you can run

```powershell
# Backend
Set-Location D:\Developer\ArtiProof\backend; python -m pytest tests -q

# Frontend
Set-Location D:\Developer\ArtiProof\frontend
npx tsc --noEmit
npm run lint
npm run test:unit
npm run test:smoke
```

Expected output:
- pytest: `381 passed, 1 deselected`
- tsc: silent (no errors)
- lint: silent (no errors)
- vitest: `Tests 20 passed (20)`
- playwright: `11 passed`

## Hand-off notes

- **No remote push.** Everything is local commits on `main`. Push when you've reviewed.
- **Author identity.** Commits are signed `Axel <exeptionnullpoint@gmail.com>` with `Co-Authored-By: Claude Opus 4.7`. Used `-c user.email/name` per-commit instead of touching your git config.
- **Migrations.** Added 0015. Same `create_type=False` enum pattern as 0014; safe to `alembic upgrade head` in any environment.
- **No env secrets touched.** `.env.example` and `JWT_SECRET`-style values are unchanged. Added one new optional setting: `OTEL_EXPORTER_OTLP_ENDPOINT` (empty default).
- **No dependencies added beyond the Phase E plan:** `opentelemetry-*`, `vitest`, `@testing-library/*`, `@vitejs/plugin-react`, `jsdom`. All scoped exactly as the plan named them.
