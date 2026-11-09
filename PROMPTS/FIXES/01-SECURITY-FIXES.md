# Phase 1: Security Fixes
## Priority: CRITICAL — Do this first

This phase fixes all exposed credentials, authorization bypasses, and security misconfigurations in the ArtiProof project. These are the most dangerous issues in the codebase.

---

## Context

ArtiProof is a Research Integrity Platform (Next.js frontend, FastAPI backend, PostgreSQL, Redis). The project has production credentials exposed in source code, missing authorization checks, and several security holes that must be fixed before any public deployment.

---

## Issues To Fix (16 total)

### 1. Remove All Hardcoded Credentials

**1a. Shell scripts with Neon database password**
Files: `import.sh`, `import2.sh`, `import3.sh`, `import4.sh`, `check.sh`, `cleanup.sh`, `clear.sh`, `final-check.sh`

All contain hardcoded Neon credentials:
```
Host: ep-steep-pine-alxrt1tl.c-3.eu-central-1.aws.neon.tech
User: neondb_owner
Password: npg_h8unbdtCSj3Q
Database: neondb
```

**Fix:** Replace all hardcoded values with environment variable references:
```bash
DB_HOST="${NEON_HOST:?NEON_HOST not set}"
DB_USER="${NEON_USER:?NEON_USER not set}"
DB_PASS="${NEON_PASSWORD:?NEON_PASSWORD not set}"
DB_NAME="${NEON_DB:?NEON_DB not set}"
```
Add a `.env.example` at project root documenting all required env vars.

**1b. Google OAuth secret in frontend**
File: `frontend/.env.local`
Contains: `GOOGLE_CLIENT_SECRET=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`

**Fix:** 
- Remove the actual secret value from `.env.local`
- Replace with placeholder: `GOOGLE_CLIENT_SECRET=your-google-client-secret-here`
- Ensure `frontend/.env.local` is in `.gitignore`
- The client secret should only exist in server-side env (NextAuth handles this)

**1c. Google Client ID hardcoded in backend config**
File: `backend/app/config.py:21`
Contains the actual Google Client ID as a default value.

**Fix:** Remove the default value, make it required:
```python
GOOGLE_CLIENT_ID: str = ""  # Required: set via GOOGLE_CLIENT_ID env var
```

**1d. JWT secret is "change-me-in-production"**
File: `backend/app/config.py:28`

**Fix:** Remove the default value and add startup validation:
```python
JWT_SECRET: str = ""  # Required: set via JWT_SECRET env var
```
In `main.py` startup, change the warning to a hard fail in production:
```python
if not settings.JWT_SECRET or settings.JWT_SECRET == "change-me-in-production":
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise RuntimeError("JWT_SECRET must be set in production")
    else:
        logger.warning("⚠️ Using insecure JWT secret — set JWT_SECRET for production")
```

**1e. Scopus API key in .env**
File: `.env`
Contains: `SCOPUS_API_KEY=11c5826ff97636c109db93a7a0922549`

**Fix:** Replace with placeholder in `.env.example`. Remove real key from `.env`.

**1f. Demo password in source code**
File: `backend/app/routers/seed.py:34`
Contains bcrypt hash for `demo1234`.

**Fix:** Move demo credentials to environment variables:
```python
DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@artiproof.com")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demo1234")
# Hash at runtime instead of hardcoding
hashed = bcrypt.hash(DEMO_PASSWORD)
```

**1g. Email in HTTP user-agent**
File: `backend/app/services/source_verification/citation_analyzer.py:61`
Contains: `info@artiproof.com` in User-Agent header.

**Fix:** Move to config:
```python
headers = {"User-Agent": f"ArtiProof/1.0 (mailto:{settings.CONTACT_EMAIL})"}
```

---

### 2. Add Authorization Checks

**2a. Source check ownership verification**
File: `backend/app/routers/source_check.py:164`

The `get_source_check` endpoint has no auth — anyone with a check ID can view any user's results.

**Fix:** Add `current_user` dependency and verify ownership:
```python
@router.get("/{check_id}")
async def get_source_check(
    check_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check = await db.get(SourceCheck, check_id)
    if not check:
        raise HTTPException(404, "Check not found")
    if check.user_id != current_user.id:
        raise HTTPException(403, "Not authorized to view this check")
    return check
```

Note: The share token endpoint (`/report/[shareToken]`) should remain public — that's intentional for sharing.

**2b. Researcher profile ownership verification**
File: `backend/app/routers/researcher.py`

Same issue — add ownership check on GET endpoints. The analysis results should only be visible to the user who created them.

**2c. Prevent user role self-escalation**
File: `backend/app/routers/auth.py` — PUT `/api/auth/me`

Users can currently set their own `role` field to "admin".

**Fix:** Strip `role` from the update payload:
```python
@router.put("/me")
async def update_profile(data: UserUpdate, ...):
    # Never allow users to change their own role
    update_data = data.dict(exclude_unset=True)
    update_data.pop("role", None)  # Remove role from updates
    ...
```

---

### 3. Secure the Seed Endpoint

File: `backend/app/routers/seed.py`

The `/api/seed/demo` and `/api/seed/all` endpoints are completely public. Anyone can call them to reset the database.

**Fix:** Add environment check — only allow in development:
```python
@router.post("/demo")
async def seed_demo(db: AsyncSession = Depends(get_db)):
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise HTTPException(403, "Seed endpoint disabled in production")
    # ... existing seed logic
```

Alternatively, require admin auth:
```python
@router.post("/demo")
async def seed_demo(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(403, "Admin access required")
    ...
```

---

### 4. Fix CORS Configuration

File: `backend/app/main.py`

Current config is dangerously permissive:
```python
allow_methods=["*"]
allow_headers=["*"]
allow_credentials=True
```

**Fix:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)
```

---

### 5. Add Rate Limiting on Auth Endpoints

File: `backend/app/routers/auth.py`

No rate limiting exists. Login endpoint is vulnerable to brute force.

**Fix:** Install `slowapi` and add rate limits:
```bash
pip install slowapi
```

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, data: LoginRequest, ...):
    ...

@router.post("/register")
@limiter.limit("3/minute")
async def register(request: Request, data: RegisterRequest, ...):
    ...
```

Add `slowapi` to `requirements.txt`.

---

### 6. Fix Redis Security

File: `docker-compose.yml`

Redis is running without authentication on exposed port 6379.

**Fix:** Add password and restrict port:
```yaml
redis:
  image: redis:7-alpine
  command: redis-server --requirepass ${REDIS_PASSWORD:-artiproof-redis-dev}
  ports:
    - "127.0.0.1:6379:6379"  # Only accessible from localhost
  ...
```

Update backend config to use Redis password in connection string.

---

### 7. Create .env.example

Create a `.env.example` at project root documenting ALL required environment variables with placeholder values. Include comments explaining each one.

---

### 8. Update .gitignore

Ensure these are in `.gitignore`:
```
.env
.env.local
frontend/.env.local
*.pid
```

---

## Verification

After completing all fixes:
1. `grep -r "npg_h8unbdtCSj3Q" .` should return 0 results
2. `grep -r "GOCSPX-" .` should return 0 results (except .env.example placeholders)
3. `grep -r "change-me-in-production" .` should return 0 results
4. `grep -r "11c5826ff97636c109db93a7a0922549" .` should return 0 results
5. The seed endpoint should return 403 when `ENVIRONMENT=production`
6. Accessing another user's source check should return 403
7. PUT `/api/auth/me` with `{"role": "admin"}` should NOT change the role
