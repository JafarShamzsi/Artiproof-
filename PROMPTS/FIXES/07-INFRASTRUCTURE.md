# Phase 7: Infrastructure Fixes
## Priority: MEDIUM — Production readiness

This phase fixes Docker configuration, dependency management, deployment config, logging, and monitoring.

---

## Issues To Fix (12 total)

### 1. Fix Docker Compose Security

File: `docker-compose.yml`

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: artiproof-postgres
    environment:
      POSTGRES_USER: ${DB_USER:-artiproof}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-artiproof-dev}  # Use env var
      POSTGRES_DB: ${DB_NAME:-artiproof}
    ports:
      - "127.0.0.1:5432:5432"  # Bind to localhost only
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-artiproof}"]
      interval: 5s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1.0"

  redis:
    image: redis:7-alpine
    container_name: artiproof-redis
    command: redis-server --requirepass ${REDIS_PASSWORD:-artiproof-redis-dev}
    ports:
      - "127.0.0.1:6379:6379"  # Bind to localhost only
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD:-artiproof-redis-dev}", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: "0.5"

  backend:
    build: ./backend
    container_name: artiproof-backend
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://${DB_USER:-artiproof}:${DB_PASSWORD:-artiproof-dev}@postgres:5432/${DB_NAME:-artiproof}
      REDIS_URL: redis://:${REDIS_PASSWORD:-artiproof-redis-dev}@redis:6379/0
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: on-failure
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: "2.0"
```

### 2. Pin Dependency Versions

File: `backend/requirements.txt`

Change all `>=` to specific version pins with upper bounds:
```
fastapi>=0.115.6,<1.0
sqlalchemy[asyncio]>=2.0.36,<2.1
pydantic>=2.10.4,<3.0
uvicorn>=0.34.2,<1.0
python-jose[cryptography]>=3.3.0,<4.0
bcrypt>=4.2.1,<5
passlib[bcrypt]>=1.7.4,<2.0
httpx>=0.28.1,<1.0
google-generativeai>=0.8.4,<1.0
PyMuPDF>=1.24.0,<2.0
beautifulsoup4>=4.13.3,<5.0
celery[redis]>=5.4.0,<6.0
slowapi>=0.1.9,<1.0  # NEW: rate limiting
```

Consider using `pip-compile` or `poetry` for a lock file:
```bash
pip install pip-tools
pip-compile requirements.in -o requirements.txt
```

### 3. Create .env.example at Project Root

File: `.env.example`

```bash
# ArtiProof Environment Configuration
# Copy this to .env and fill in real values

# === Database ===
DB_USER=artiproof
DB_PASSWORD=change-me
DB_HOST=localhost
DB_PORT=5432
DB_NAME=artiproof
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
DATABASE_URL_SYNC=postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}

# === Redis ===
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=change-me

# === Auth ===
JWT_SECRET=generate-a-random-64-char-string-here
JWT_ALGORITHM=HS256

# === Google OAuth ===
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# === API Keys ===
GEMINI_API_KEY=your-gemini-api-key
SCOPUS_API_KEY=your-scopus-api-key  # Optional
SEMANTIC_SCHOLAR_API_KEY=  # Optional, uses public API

# === App URLs ===
APP_URL=http://localhost:3000
API_URL=http://localhost:8000

# === Environment ===
ENVIRONMENT=development  # development | production

# === Contact ===
CONTACT_EMAIL=info@artiproof.com

# === Neon (Production DB) ===
# NEON_HOST=your-neon-host
# NEON_USER=your-neon-user
# NEON_PASSWORD=your-neon-password
# NEON_DB=your-neon-db
```

### 4. Fix run.sh Container Names

File: `run.sh`

Replace all `civicguards-*` references with `artiproof-*`:
```bash
# Replace:
docker exec civicguards-postgres ...
docker exec civicguards-redis ...

# With:
docker exec artiproof-postgres ...
docker exec artiproof-redis ...
```

Also update the demo credentials output:
```bash
echo "  Email:    demo@artiproof.com"
```

### 5. Add Logging Configuration

File: `backend/app/main.py`

```python
import logging
import sys

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Reduce noise from third-party libs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
```

### 6. Add Request Logging Middleware

```python
import time

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    
    # Log all non-health requests
    if request.url.path not in ("/health", "/api/health"):
        logger.info(
            f"{request.method} {request.url.path} "
            f"status={response.status_code} "
            f"duration={duration:.3f}s "
            f"ip={request.client.host if request.client else 'unknown'}"
        )
    
    return response
```

### 7. Add Graceful Shutdown

```python
@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down ArtiProof backend...")
    # Close database connections
    # Close Redis connections
    # Wait for in-flight requests
```

### 8. Add Frontend Security Headers

File: `frontend/next.config.ts`

```typescript
const nextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          {
            key: "Content-Security-Policy",
            value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://*.vercel.app https://generativelanguage.googleapis.com;"
          },
        ],
      },
    ];
  },
};
```

### 9. Update Railway Deployment Config

File: `backend/railway.toml`

```toml
[build]
builder = "NIXPACKS"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 30
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 5
```

### 10. Add PDF Cleanup Cron Job

Create: `backend/app/tasks/cleanup.py`

```python
import os
import time
from pathlib import Path

UPLOAD_DIR = Path("uploads")
MAX_AGE_HOURS = 24

async def cleanup_old_files():
    """Remove uploaded/annotated PDFs older than 24 hours."""
    now = time.time()
    for file in UPLOAD_DIR.rglob("*"):
        if file.is_file() and (now - file.stat().st_mtime) > MAX_AGE_HOURS * 3600:
            file.unlink()
```

### 11. Add Startup Validation

File: `backend/app/main.py`

```python
@app.on_event("startup")
async def startup():
    errors = []
    
    # Check required env vars
    if not settings.JWT_SECRET:
        errors.append("JWT_SECRET is not set")
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — analysis features disabled")
    
    # Check database connectivity
    try:
        async with get_db() as db:
            await db.execute(text("SELECT 1"))
    except Exception as e:
        errors.append(f"Database connection failed: {e}")
    
    if errors and os.getenv("ENVIRONMENT") == "production":
        for error in errors:
            logger.critical(f"STARTUP FAILURE: {error}")
        raise RuntimeError(f"Startup validation failed: {', '.join(errors)}")
```

### 12. Update .gitignore

Ensure comprehensive .gitignore:
```
# Environment
.env
.env.local
.env.production
frontend/.env.local

# Python
__pycache__/
*.pyc
venv/
.venv/

# Node
node_modules/
.next/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Uploads
uploads/
annotated/

# PIDs
*.pid

# Logs
*.log
```

---

## Verification

1. `docker-compose up` starts all services with health checks passing
2. Redis requires password to connect
3. PostgreSQL only accepts connections from localhost
4. `.env.example` exists at project root with all variables documented
5. `run.sh` references correct container names
6. Request logs appear in stdout
7. Health check verifies DB and Redis connectivity
8. Security headers present in frontend responses
