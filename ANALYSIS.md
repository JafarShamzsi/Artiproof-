# ArtiProof — Codebase Analysis

_Generated 2026-05-30. AI-powered legal/contract review platform (FastAPI + React)._

## What it is

A monorepo with a **React 19 + Vite + TS** frontend at the root and a **FastAPI** backend under `backend/`. Users register/login (JWT), create Projects, upload Documents (PDF/DOCX/text → text extraction), and run AI Analyses that return JSON findings with severity + a 0–100 score. Data model: User → Project → Document → Analysis. Spec lives in `a.txt`.

## Overall state

The scaffolding is clean and the architecture is sensible (layered backend, typed schemas, protected routes). But it is **not runnable end-to-end** — there are blocking bugs and several backend endpoints the frontend calls don't exist yet.

---

## Blocking bugs (app won't work until fixed)

1. **Database tables are never created.** No `Base.metadata.create_all`, no Alembic migrations, no migration scripts. First DB query will fail with "no such table: users". Either add Alembic (spec mentions it) or call `create_all` on startup for dev.

2. **`GET /api/v1/analysis/{id}` is missing.** `AnalysisPage.tsx` calls it, but `analysis.py` only implements `POST /{document_id}`. The analysis view will 404.

3. **`GET /api/v1/projects/{id}/documents` is missing.** `ProjectDetailPage.tsx` calls it (to list docs + trigger analysis), but `projects.py` has no such route. The project detail page will 404.

4. **Likely passlib/bcrypt break.** `passlib 1.7.4` + modern `bcrypt` (4.x) throws on hashing in many setups. Pin `bcrypt<4` or migrate to `bcrypt`/`argon2` directly.

---

## Security issues

- **Hardcoded default `SECRET_KEY`** in `config.py` ("your-secret-key-change-this-in-production"). Anyone can forge JWTs if it ships unchanged. Make it required, no default.
- **JWT in `localStorage`** (`api.ts`, `AuthContext`) — vulnerable to XSS token theft. Consider httpOnly cookies.
- **`MAX_UPLOAD_SIZE` is defined but never enforced** in `upload.py` — unbounded uploads read fully into memory (`await file.read()`). DoS risk.
- **CORS `allow_credentials=True`** with permissive methods/headers; fine for localhost but tighten for prod.
- No rate limiting on `/auth/login` (brute-force) or `/analysis` (cost abuse).

---

## Correctness / quality gaps

- **Analysis runs synchronously inside the request** — a slow OpenAI call blocks the worker. Move to a background task (FastAPI `BackgroundTasks` / a queue) and have the frontend poll, which also matches the `status: pending/completed/failed` design.
- **`datetime.utcnow()` is deprecated** (Py 3.12+). Use `datetime.now(timezone.utc)`.
- `result_json` is returned as a **raw string**; frontend must `JSON.parse`. Consider returning a parsed object via a validated schema.
- **No documents/analyses list endpoints** beyond the two missing ones (e.g. list analyses per document).
- **No pagination** on project/document lists.
- `useAuth()` uses a non-null assertion (`!`) — throws unhelpfully if used outside provider.
- No error boundary; `AnalysisPage` doesn't render the `failed` state.

---

## Tooling / hygiene

- **No tests** — `test_main.py` / `test_setup.py` are `assert True` placeholders. No frontend tests.
- **No CI, no Docker, no Alembic** (all marked TODO in spec).
- **README is default Vite boilerplate**, and there's a duplicate `README copy.md`. The real spec is in `a.txt` — should become proper `README.md` + `/docs`.
- **`package.json` lists `@radix-ui/react-slot` twice**; deps could be deduped.
- `.env.local` is committed (only contains the non-secret API base URL, but it's gitignored — confusing to have both).

---

## Suggested roadmap

**Phase 1 — Make it run (blocking):** add Alembic (or dev `create_all`); implement `GET /analysis/{id}` and `GET /projects/{id}/documents`; fix bcrypt pin. _Goal: full happy-path works locally._

**Phase 2 — Harden security:** required `SECRET_KEY`, enforce upload size, login rate limiting, review token storage.

**Phase 3 — Async analysis:** background tasks + status polling + proper failed-state UI.

**Phase 4 — Quality:** real tests (pytest + Vitest), CI, Docker, clean README/docs, dedupe deps.

**Phase 5 — Product depth:** clause-level highlighting, analysis history/audit trail, export findings, team sharing.
