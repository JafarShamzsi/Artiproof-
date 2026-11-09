# Phase 9: Polish & Cleanup
## Priority: LOW — Nice to have

This phase cleans up code quality, removes unused code, adds documentation, and implements remaining missing features.

---

## Issues To Fix (6 groups)

### 1. Remove Unused Components

Check and remove if truly unused:
- `frontend/src/components/landing/EngineGrid.tsx` — exists but not imported in landing page
- `frontend/src/components/landing/EducationSection.tsx` — same

Before deleting, check if they're imported anywhere:
```bash
grep -r "EngineGrid" frontend/src/
grep -r "EducationSection" frontend/src/
```

If zero results besides the file itself, delete them.

### 2. Extract Magic Numbers Into Constants

Create: `backend/app/constants.py`

```python
# Claim extraction
MAX_TEXT_LENGTH = 15_000
MAX_CLAIMS = 15

# AI detection
MAX_PARAGRAPHS_AI_DETECTION = 20
DEFAULT_AI_PROBABILITY = 0.5

# Citation ring detection
DEFAULT_MUTUAL_CITATION_THRESHOLD = 5
DEFAULT_SELF_CITATION_WARN_RATE = 0.15
DEFAULT_SELF_CITATION_FLAG_RATE = 0.25
DEFAULT_CITATION_VELOCITY_THRESHOLD = 50

# Researcher analysis
MAX_PUBLICATIONS_TO_ANALYZE = 100
PUBLICATION_BATCH_SIZE = 20

# File upload
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Scoring
CREDIBILITY_SCORE_MIN = 0
CREDIBILITY_SCORE_MAX = 100
```

Replace all hardcoded numbers throughout the codebase with these constants.

### 3. Centralize Frontend Color Utilities

Create: `frontend/src/lib/colors.ts`

```typescript
export const scoreColor = (score: number) =>
  score >= 70 ? "text-emerald-400" : score >= 40 ? "text-yellow-400" : "text-red-400";

export const scoreBgColor = (score: number) =>
  score >= 70 ? "bg-emerald-500" : score >= 40 ? "bg-yellow-500" : "bg-red-500";

export const scoreStroke = (score: number) =>
  score >= 70 ? "#10b981" : score >= 40 ? "#eab308" : "#ef4444";

export const aiProbColor = (prob: number) =>
  prob > 0.7 ? "text-red-400" : prob > 0.3 ? "text-yellow-400" : "text-emerald-400";

export const verdictColor = (verdict: string) => ({
  true: "text-emerald-400",
  false: "text-red-400",
  misleading: "text-yellow-400",
  unverifiable: "text-zinc-400",
  unknown: "text-zinc-500",
}[verdict] || "text-zinc-400");
```

Remove duplicate definitions from:
- `frontend/src/app/(dashboard)/check/[id]/page.tsx`
- `frontend/src/app/(dashboard)/researcher/[id]/page.tsx`
- `frontend/src/components/landing/ScannerPreview.tsx`

### 4. Add API Documentation

File: `backend/app/main.py`

Add OpenAPI metadata:
```python
app = FastAPI(
    title="ArtiProof API",
    description="Research Integrity Platform — Source verification, AI detection, citation analysis, and researcher integrity scoring.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
```

Add descriptions to route tags:
```python
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(source_check_router, prefix="/api/source-check", tags=["Source Verification"])
app.include_router(researcher_router, prefix="/api/researcher", tags=["Researcher Integrity"])
```

Add docstrings to all endpoint functions for auto-documentation.

### 5. Add README.md

Create `README.md` at project root:

```markdown
# ArtiProof

Research Integrity Platform — 5 tools in one.

## Features
- Plagiarism detection
- AI content detection
- Citation ring detection
- Researcher integrity scoring
- Fact-checking with evidence

## Quick Start

1. Copy `.env.example` to `.env` and fill in values
2. `docker-compose up -d`
3. `cd frontend && npm install && npm run dev`
4. Open http://localhost:3000

## Tech Stack
- **Frontend:** Next.js 14, React 19, Tailwind CSS, Framer Motion
- **Backend:** FastAPI, SQLAlchemy, PostgreSQL, Redis
- **AI:** Google Gemini, Google Fact Check API
- **APIs:** Semantic Scholar, CrossRef, ORCID

## Architecture
- `frontend/` — Next.js app
- `backend/` — FastAPI server
- `backend/app/services/source_verification/` — Source check pipeline
- `backend/app/services/academic_integrity/` — Researcher analysis pipeline
```

### 6. Clean Up Import Scripts

Consolidate `import.sh`, `import2.sh`, `import3.sh`, `import4.sh` into one script:

File: `import-data.sh`
```bash
#!/bin/bash
set -euo pipefail

DB_HOST="${NEON_HOST:?NEON_HOST not set}"
DB_USER="${NEON_USER:?NEON_USER not set}"
DB_NAME="${NEON_DB:?NEON_DB not set}"

echo "Importing data to $DB_HOST/$DB_NAME..."

# Clean SQL dump (remove trigger and session auth lines)
sed '/DISABLE TRIGGER/d; /ENABLE TRIGGER/d; /SET SESSION AUTHORIZATION/d' \
  data-ordered.sql > /tmp/clean-import.sql

PGPASSWORD="${NEON_PASSWORD:?}" psql \
  -h "$DB_HOST" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  --set ON_ERROR_STOP=1 \
  -f /tmp/clean-import.sql

echo "Import complete."
rm /tmp/clean-import.sql
```

Delete the old `import*.sh` files.

---

## Final Verification Checklist

After all 9 phases are complete, verify:

### Landing Page
- [ ] Pricing: Free ($0), Pro ($20/mo highlighted), Institution (Custom/Contact Sales)
- [ ] Stats: 14K+, 92%, $392K, < 2min — all sourced
- [ ] No mention of "free for researchers and institutions" outside Free tier
- [ ] Footer links work or are removed
- [ ] Competitor comparison table visible
- [ ] Hero mentions "51 universities" and "222,809 students"

### Security
- [ ] `grep -r "npg_h8unbdtCSj3Q" .` → 0 results
- [ ] `grep -r "GOCSPX-" . --include="*.ts" --include="*.py"` → 0 results
- [ ] Seed endpoint disabled in production
- [ ] Source check ownership verified
- [ ] User cannot self-escalate role
- [ ] Rate limiting on auth endpoints

### Database
- [ ] Alembic migrations exist and run
- [ ] Indexes on status and created_at columns
- [ ] Score breakdown columns exist

### Backend
- [ ] Score breakdown returned in API responses
- [ ] Model metadata stored per analysis
- [ ] Retry logic on external API calls
- [ ] PDF validation before processing
- [ ] ORCID format validation

### Frontend
- [ ] No `any[]` types
- [ ] 404 and error pages exist
- [ ] EventSource cleanup on unmount
- [ ] File upload errors displayed
- [ ] Publications paginated
- [ ] Security headers in responses

### Tests
- [ ] `pytest tests/` passes
- [ ] Scoring tests cover edge cases
- [ ] API endpoint tests verify auth

### Infrastructure
- [ ] `.env.example` exists
- [ ] `.gitignore` covers all sensitive files
- [ ] Docker services have resource limits
- [ ] Redis requires authentication
- [ ] Health check verifies DB and Redis
