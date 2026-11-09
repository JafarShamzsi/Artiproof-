# CivicGuards — Production Finalization Prompt

## IMPORTANT: Read PROMPTS/REBUILD-PROMPT.md first for full project context.

This is the FINAL pass to fix everything broken, connect everything disconnected, and make the app production-ready for hackathon presentation. Go through EVERY item below. Don't skip anything. Test after each section.

---

## CRITICAL ISSUE 1: Database Has No Migrations

The Alembic `versions/` directory is EMPTY. No tables exist in the database. This means nothing works.

**Fix:**
```bash
cd backend
alembic revision --autogenerate -m "Initial schema - all tables"
alembic upgrade head
```

Verify all 11 tables are created:
- users
- source_checks
- claim_analyses
- ai_detection_results
- citation_checks
- researcher_profiles
- publication_analyses
- scraped_publications
- citation_edges
- coauthor_relations
- reports

If autogenerate doesn't pick up all models, check that `backend/app/models/__init__.py` imports every model class so Alembic's `env.py` can see them. If needed, update `env.py` to import `from app.models import *` or import each model explicitly.

After migration, verify with:
```bash
alembic current  # should show the migration hash
```

---

## CRITICAL ISSUE 2: Auth Endpoints Are All Stubbed (Return 501)

File: `backend/app/routers/auth.py`

ALL 4 auth endpoints currently raise `HTTPException(status_code=501)`. Implement them fully:

### POST /api/auth/register
```python
from passlib.hash import bcrypt
from app.models.user import User
from cuid2 import cuid_wrapper

generate_id = cuid_wrapper()

@router.post("/register", response_model=UserResponse, status_code=201)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check if email already exists
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    
    # Create user
    user = User(
        id=generate_id(),
        email=data.email,
        hashed_password=bcrypt.hash(data.password),
        full_name=data.full_name,
        institution=data.institution,
        role=data.role or "researcher",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
```

### POST /api/auth/login
```python
import jwt
from datetime import datetime, timedelta
from app.config import settings

@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await db.execute(select(User).where(User.email == data.email))
    user = user.scalar_one_or_none()
    
    if not user or not bcrypt.verify(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = jwt.encode(
        {"sub": user.id, "email": user.email, "exp": datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"access_token": token, "token_type": "bearer"}
```

### GET /api/auth/me + PUT /api/auth/me
```python
from app.utils.auth import get_current_user  # create this dependency (see below)

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_profile(data: UserUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.institution is not None:
        current_user.institution = data.institution
    if data.role is not None:
        current_user.role = data.role
    if data.high_contrast is not None:
        current_user.high_contrast = data.high_contrast
    await db.commit()
    await db.refresh(current_user)
    return current_user
```

### Create JWT Auth Dependency

Create `backend/app/utils/auth.py`:
```python
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models.user import User

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Same as above but returns None instead of 401 — for endpoints that work with or without auth."""
    if not credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        return await db.get(User, user_id)
    except Exception:
        return None
```

Add `PyJWT` to `requirements.txt` if not already present.

---

## CRITICAL ISSUE 3: All Routers Hardcode "demo-user"

Every router file uses `user_id = "demo-user"` instead of extracting from JWT.

**Fix ALL of these files:**

1. `backend/app/routers/source_check.py` — 3 occurrences
2. `backend/app/routers/researcher.py` — 2 occurrences (already has TODO comments)
3. `backend/app/routers/dashboard.py` — 3 occurrences
4. `backend/app/routers/reports.py` — 2 occurrences
5. `backend/app/routers/seed.py` — 1 occurrence

In each file:
1. Add import: `from app.utils.auth import get_current_user`
2. Add `current_user: User = Depends(get_current_user)` to endpoint function signature
3. Replace `user_id = "demo-user"` with `user_id = current_user.id`

Example for `source_check.py`:
```python
# BEFORE:
@router.post("/")
async def create_source_check(data: SourceCheckCreate, db: AsyncSession = Depends(get_db)):
    user_id = "demo-user"
    ...

# AFTER:
@router.post("/")
async def create_source_check(data: SourceCheckCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    ...
```

Do this for EVERY endpoint in ALL 5 router files listed above.

---

## CRITICAL ISSUE 4: Frontend Auth Doesn't Connect to Backend

The frontend uses NextAuth for session management, but the backend auth endpoints were stubbed. Now that we're implementing them, we need to make sure the frontend actually calls the backend.

### Fix NextAuth Configuration

Check `frontend/src/app/api/auth/[...nextauth]/route.ts` — the CredentialsProvider must call the backend `/api/auth/login` endpoint:

```typescript
import NextAuth from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

const handler = NextAuth({
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: credentials?.email,
            password: credentials?.password,
          }),
        });

        if (!res.ok) return null;

        const data = await res.json();
        
        // Now get user profile using the token
        const profileRes = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/api/auth/me`, {
          headers: { Authorization: `Bearer ${data.access_token}` },
        });
        
        if (!profileRes.ok) return null;
        const user = await profileRes.json();

        return {
          id: user.id,
          name: user.full_name,
          email: user.email,
          accessToken: data.access_token,
          institution: user.institution,
          role: user.role,
        };
      },
    }),
  ],
  session: { strategy: "jwt" },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = user.accessToken;
        token.userId = user.id;
        token.institution = user.institution;
        token.role = user.role;
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken;
      session.user.id = token.userId;
      session.user.institution = token.institution;
      session.user.role = token.role;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
});

export { handler as GET, handler as POST };
```

### Fix Frontend Register Page

The register page must call the backend `/api/auth/register` and then sign in:

```typescript
// In register/page.tsx — the form submit handler:
async function onSubmit(e) {
  e.preventDefault();
  setLoading(true);
  setError(null);

  // 1. Register with backend
  const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, full_name: fullName, institution, role }),
  });

  if (!res.ok) {
    const data = await res.json();
    setError(data.detail || "Registration failed");
    setLoading(false);
    return;
  }

  // 2. Auto sign in after registration
  const result = await signIn("credentials", {
    email,
    password,
    redirect: false,
  });

  if (result?.error) {
    setError("Registration succeeded but login failed. Please sign in manually.");
  } else {
    router.push("/dashboard");
  }
  setLoading(false);
}
```

### Pass Access Token to Backend Calls

All frontend API calls to the backend need the JWT token from the session. Create a utility:

Create `frontend/src/lib/api.ts`:
```typescript
import { getSession } from "next-auth/react";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export async function apiFetch(path: string, options: RequestInit = {}) {
  const session = await getSession();
  
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  
  if (session?.accessToken) {
    headers["Authorization"] = `Bearer ${session.accessToken}`;
  }
  
  const res = await fetch(`${BACKEND_URL}${path}`, {
    ...options,
    headers,
  });
  
  if (res.status === 401) {
    // Token expired — redirect to login
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  
  return res;
}
```

Then update ALL frontend pages that call the backend to use `apiFetch` instead of raw `fetch`:
- `check/page.tsx` — source check creation and list
- `check/[id]/page.tsx` — results fetching
- `researcher/page.tsx` — researcher analysis
- `researcher/[id]/page.tsx` — researcher results
- `reports/page.tsx` — report list
- `dashboard/page.tsx` — stats and activity
- `settings/page.tsx` — profile update

---

## CRITICAL ISSUE 5: Branding Mismatch — "ArtiProof" vs "CivicGuards"

The project is called **CivicGuards** but there are 12+ references to the old name "ArtiProof" scattered through the codebase.

**Replace ALL of these:**

### Frontend (11 occurrences):
1. `frontend/src/app/(auth)/login/page.tsx:54` — "Sign in to your ArtiProof account" → "Sign in to your CivicGuards account"
2. `frontend/src/app/(auth)/register/page.tsx:83` — "Join ArtiProof" → "Join CivicGuards"
3. `frontend/src/app/(dashboard)/layout.tsx:53` — sidebar logo text "ArtiProof" → "CivicGuards"
4. `frontend/src/app/layout.tsx:14` — page title "ArtiProof" → "CivicGuards"
5. `frontend/src/app/report/[shareToken]/page.tsx:69` — header "ArtiProof" → "CivicGuards"
6. `frontend/src/app/report/[shareToken]/page.tsx:108` — footer text "ArtiProof" → "CivicGuards"
7. `frontend/src/components/landing/Footer.tsx:43` — logo text "ArtiProof" → "CivicGuards"
8. `frontend/src/components/landing/Footer.tsx:114` — copyright "ArtiProof" → "CivicGuards"
9. `frontend/src/components/landing/Navbar.tsx:56` — desktop nav "ArtiProof" → "CivicGuards"
10. `frontend/src/components/landing/Navbar.tsx:102` — mobile nav "ArtiProof" → "CivicGuards"
11. `frontend/src/contexts/ThemeContext.tsx:12` — localStorage key "artiproof-high-contrast" → "civicguards-high-contrast"

### Docker/Infra (rename containers and DB):
12. `docker-compose.yml` — Replace ALL "artiproof" with "civicguards":
    - container names: `artiproof-postgres` → `civicguards-postgres`, `artiproof-redis` → `civicguards-redis`, `artiproof-backend` → `civicguards-backend`
    - POSTGRES_USER: `artiproof` → `civicguards`
    - POSTGRES_PASSWORD: `artiproof` → `civicguards`
    - POSTGRES_DB: `artiproof` → `civicguards`
    - DATABASE_URL strings: update both async and sync URLs
    - healthcheck: `pg_isready -U civicguards -d civicguards`
    - network name: `artiproof-network` → `civicguards-network`

### .env file:
13. Update DATABASE_URL to match if docker-compose values changed

Use find-and-replace across the entire project. Search for both `ArtiProof` (case-sensitive) and `artiproof` (lowercase).

---

## CRITICAL ISSUE 6: .env Missing API Keys

The `.env` file has empty values for critical API keys:

```env
GEMINI_API_KEY=          # EMPTY — Module 1 and Module 2 won't work at all
GOOGLE_FACTCHECK_API_KEY= # EMPTY — fact checking won't work
SEMANTIC_SCHOLAR_API_KEY= # EMPTY — ok, free tier works without key but rate-limited
```

**This is a user responsibility** — but the app must NOT crash when keys are missing. Add graceful handling:

### In every service that uses an API key, check before calling:

```python
# In fact_checker.py, ai_detector.py, claim_extractor.py, etc.:
if not settings.GEMINI_API_KEY:
    return {
        "error": "Gemini API key not configured",
        "status": "skipped",
        "message": "Configure GEMINI_API_KEY in .env to enable this analysis"
    }
```

```python
# In fact_checker.py for Google Fact Check:
if not settings.GOOGLE_FACTCHECK_API_KEY:
    # Skip Google Fact Check, rely only on Gemini analysis
    pass
```

### Add a startup health check in `backend/app/main.py`:
```python
import logging
logger = logging.getLogger("civicguards")

@app.on_event("startup")
async def startup_checks():
    warnings = []
    if not settings.GEMINI_API_KEY:
        warnings.append("GEMINI_API_KEY not set — AI analysis features disabled")
    if not settings.GOOGLE_FACTCHECK_API_KEY:
        warnings.append("GOOGLE_FACTCHECK_API_KEY not set — fact-check database lookup disabled")
    
    for w in warnings:
        logger.warning(f"⚠️  {w}")
    
    if warnings:
        logger.warning("Configure missing API keys in .env for full functionality")
```

### Add a `/api/health` endpoint:
```python
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "services": {
            "gemini": bool(settings.GEMINI_API_KEY),
            "google_factcheck": bool(settings.GOOGLE_FACTCHECK_API_KEY),
            "scopus": bool(settings.SCOPUS_API_KEY),
            "semantic_scholar": bool(settings.SEMANTIC_SCHOLAR_API_KEY),
        }
    }
```

---

## ISSUE 7: Settings Page "Save" Button Does Nothing

File: `frontend/src/app/(dashboard)/settings/page.tsx` line 22

The save button has a fake `setTimeout` instead of calling the API:

```typescript
// CURRENT (fake):
async function handleSave() {
    setSaving(true);
    // TODO: Phase 2 — call PUT /api/auth/me
    await new Promise((r) => setTimeout(r, 500));
    setSaving(false);
    setSaved(true);
}

// FIX — call the real API:
async function handleSave() {
    setSaving(true);
    try {
      const res = await apiFetch("/api/auth/me", {
        method: "PUT",
        body: JSON.stringify({
          full_name: fullName,
          institution,
          role: selectedRole,
          high_contrast: highContrast,
        }),
      });
      if (res.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      } else {
        // Show error
      }
    } catch (err) {
      console.error(err);
    }
    setSaving(false);
}
```

Also fix:
- The role `<select>` element doesn't track state — add `value={selectedRole}` and `onChange` handler
- The notification checkboxes are uncontrolled (`defaultChecked`) — make them controlled with state
- Load initial values from the user's profile on mount (call GET /api/auth/me)

---

## ISSUE 8: Citation Analyzer Missing Alternative Suggestions

File: `backend/app/services/source_verification/citation_analyzer.py` line ~169

```python
"suggested_alternative": None,  # TODO: use Gemini to suggest alternatives
```

**Fix:** After checking a citation's credibility, if the score is below 50 or the source is retracted, call Gemini to suggest a replacement:

```python
if credibility_score < 50 or is_retracted:
    if settings.GEMINI_API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            f"The following academic citation is unreliable or retracted: '{original_citation}'. "
            f"Suggest ONE specific, real, reputable alternative source on the same topic. "
            f"Return just the citation in standard academic format (Author, Year, Title, Journal)."
        )
        suggested_alternative = response.text.strip()
```

---

## ISSUE 9: Notification Preferences Not Persisted

The settings page has notification checkboxes but they don't save anywhere.

**Option A (Quick — localStorage):** Store in localStorage for now since we don't have a notifications system yet.

**Option B (Proper):** Add a `notification_preferences` JSON column to the User model:
```python
notification_preferences = Column(JSON, default={"source_check_complete": True, "researcher_complete": True, "weekly_digest": False})
```

Include it in the PUT /api/auth/me endpoint and load it on the settings page.

---

## ISSUE 10: Missing Error Boundaries & Loading States

Check every page for proper error and loading handling:

### Pages that need loading skeletons:
- `/dashboard` — while stats are loading
- `/check` — while past checks are loading
- `/check/[id]` — while results are loading (this is the big one — show a progress skeleton)
- `/researcher` — while past analyses are loading
- `/researcher/[id]` — while profile is loading
- `/reports` — while report list is loading

### Pages that need error states:
Every page that calls `apiFetch` needs a try/catch with a user-friendly error message:
```tsx
{error && (
  <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4 text-red-400">
    <p className="font-medium">Something went wrong</p>
    <p className="text-sm">{error}</p>
    <Button onClick={retry} className="mt-2">Try Again</Button>
  </div>
)}
```

### Global error boundary:
Create `frontend/src/components/ErrorBoundary.tsx` — a React error boundary that catches rendering errors and shows a friendly fallback instead of a white screen.

---

## ISSUE 11: CORS Configuration

The FastAPI backend needs CORS configured to accept requests from the Next.js frontend:

Check `backend/app/main.py` for CORSMiddleware. If missing or incomplete, add:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://civicguards.vercel.app",  # production frontend URL
        settings.APP_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## ISSUE 12: Docker Compose Missing Celery Worker & Frontend

The current `docker-compose.yml` only has postgres, redis, and backend. It's missing:

### Add Celery worker service:
```yaml
  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: civicguards-celery
    restart: unless-stopped
    command: celery -A app.tasks worker --loglevel=info
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+asyncpg://civicguards:civicguards@postgres:5432/civicguards
      DATABASE_URL_SYNC: postgresql://civicguards:civicguards@postgres:5432/civicguards
      REDIS_URL: redis://redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - civicguards-network
```

### Add frontend service (optional for Docker deployment):
```yaml
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: civicguards-frontend
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_BACKEND_URL: http://backend:8000
      NEXTAUTH_URL: http://localhost:3000
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
    depends_on:
      - backend
    networks:
      - civicguards-network
```

### Create frontend Dockerfile if it doesn't exist:
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

---

## ISSUE 13: Seed Data for Demo

The app needs demo data so it doesn't look empty during the hackathon presentation.

### Create a seed endpoint or script that populates:

1. **Demo user account:**
   - Email: demo@civicguards.az
   - Password: demo2026
   - Name: Demo Researcher
   - Institution: ADA University
   - Role: researcher

2. **3-4 completed source checks** with varying credibility scores:
   - One with high credibility (85+) — a real, well-sourced article
   - One with low credibility (30-40) — contains misinformation
   - One with AI-detected content (60% AI)
   - Each should have claims, AI detection results, and citation checks fully populated

3. **2-3 completed researcher analyses:**
   - One clean researcher with high integrity score
   - One suspicious researcher with citation ring patterns and inflated metrics
   - Each should have publications, citation edges, and co-author relations populated

4. **1-2 generated reports** with PDF files

### Create seed script:
```bash
# backend/scripts/seed_demo.py
# Run with: python -m scripts.seed_demo
```

Or add a protected endpoint:
```python
@router.post("/api/seed/demo")
async def seed_demo_data(db: AsyncSession = Depends(get_db)):
    # Only works in development
    if settings.APP_ENV == "production":
        raise HTTPException(403, "Cannot seed in production")
    # ... seed data ...
    return {"status": "seeded"}
```

---

## ISSUE 14: Frontend — Shared Report Page Polish

File: `frontend/src/app/report/[shareToken]/page.tsx`

This page needs to work WITHOUT authentication (it's a public link). Verify:
- It does NOT require a session/JWT
- It calls `GET /api/reports/shared/{shareToken}` which also doesn't require auth
- It renders all report data properly (source check OR researcher analysis)
- The page has CivicGuards branding (logo, footer)
- It has a "Download PDF" button that works

---

## ISSUE 15: SSE Streaming Error Handling

Both `/api/source-check/{id}/stream` and `/api/researcher/{id}/stream` use Server-Sent Events. Verify:

1. **Connection drops:** If the browser disconnects, the SSE generator should stop gracefully (not keep running)
2. **Error events:** If the backend pipeline fails, send an SSE event with `event: error` and close the stream
3. **Completion:** Send a final `event: complete` event so the frontend knows to stop listening
4. **Frontend reconnection:** If SSE disconnects unexpectedly, the frontend should try to reconnect once, then fall back to polling the check status every 5 seconds

---

## ISSUE 16: Mobile Responsiveness

Check these pages on small screens (< 768px):

1. **Dashboard** — stats cards should stack vertically (2 per row → 1 per row)
2. **Check source results** — the split-view PDF layout should switch to a tabbed layout on mobile (Report tab / Document tab)
3. **Researcher results** — citation graph should be scrollable/zoomable on mobile
4. **Landing page** — hero section, feature cards, pricing grid should all be responsive
5. **Sidebar** — already has Sheet (mobile drawer) — verify it works and closes on navigation

---

## ISSUE 17: Landing Page — Content Alignment

The landing page sections need to reflect the CURRENT product (Research Integrity Platform). Verify all text matches our two-module description:

1. Hero tagline should mention research integrity, not generic security
2. "How it works" should show: Paste Source → AI Analysis → Integrity Report
3. Feature cards should map to our actual features (misinfo detection, AI detection, citation rings, adjusted ratings)
4. "Who it's for" should list: Researchers, Faculty, PhD Students, Institutions
5. Pricing/CTA should be relevant (not mentioning features we don't have)

If any section still references old concepts (security scanning, threat intelligence, etc.), update them.

---

## ISSUE 18: Production Environment Variables

Create a `.env.example` file at the project root that documents ALL required and optional variables:

```env
# === REQUIRED ===
DATABASE_URL=postgresql+asyncpg://civicguards:civicguards@localhost:5432/civicguards
DATABASE_URL_SYNC=postgresql://civicguards:civicguards@localhost:5432/civicguards
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=CHANGE-THIS-TO-A-RANDOM-SECRET
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=CHANGE-THIS-TO-A-RANDOM-SECRET
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
APP_URL=http://localhost:3000
API_URL=http://localhost:8000

# === REQUIRED FOR FULL FUNCTIONALITY ===
GEMINI_API_KEY=your-gemini-api-key
GOOGLE_FACTCHECK_API_KEY=your-google-factcheck-key

# === OPTIONAL (improves data quality) ===
SCOPUS_API_KEY=
SEMANTIC_SCHOLAR_API_KEY=

# === OPTIONAL (OAuth login) ===
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

# === APP CONFIG ===
APP_ENV=development
GEMINI_MODEL=gemini-2.0-flash
```

---

## ISSUE 19: Backend Startup — Import & Config Validation

Run the backend and fix any import errors:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Fix ANY import errors, missing modules, or startup crashes. Common issues:
- Missing model imports in `__init__.py`
- Circular imports between models
- Config values referenced but not defined in settings
- Missing `passlib`, `PyJWT`, `networkx` in requirements.txt

Then verify ALL endpoints respond:
```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/docs  # Swagger UI should load
```

---

## ISSUE 20: Frontend Build Check

```bash
cd frontend
npm install
npm run build
```

Fix ANY TypeScript errors, missing imports, or build failures. Common issues:
- Type mismatches in NextAuth session augmentation (need `next-auth.d.ts` declaration file)
- Missing environment variables at build time
- Import paths that don't resolve

---

## EXECUTION ORDER

Do these in this EXACT order (dependencies matter):

1. **Branding rename** (ArtiProof → CivicGuards) — affects everything
2. **Database migrations** — nothing else works without tables
3. **Auth implementation** (backend endpoints + JWT dependency)
4. **Connect frontend auth to backend** (NextAuth config + register page + apiFetch utility)
5. **Replace demo-user in all routers** with JWT extraction
6. **Fix settings page** save button
7. **Fix citation analyzer** TODO
8. **Add CORS middleware** if missing
9. **Add health endpoint** + API key validation
10. **Update docker-compose** (rename + add celery worker)
11. **Create .env.example**
12. **Add error boundaries and loading states** to all pages
13. **SSE error handling**
14. **Mobile responsiveness check**
15. **Landing page content verification**
16. **Seed demo data**
17. **Full build test** — `npm run build` frontend + `uvicorn` backend
18. **End-to-end smoke test:** Register → Login → Create source check → View results → Create researcher analysis → View results → Generate report → Share report → Open shared link
