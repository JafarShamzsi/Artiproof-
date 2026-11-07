import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    auth_router,
    source_check_router,
    researcher_router,
    reports_router,
    dashboard_router,
)
from app.routers.seed import router as seed_router

logger = logging.getLogger("artiproof")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warn about missing API keys — the app still starts, but services will return
    # a "skipped" status rather than crash.
    missing = []
    if not settings.GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY — AI claim/citation/content analysis disabled")
    if not settings.GOOGLE_FACTCHECK_API_KEY:
        missing.append("GOOGLE_FACTCHECK_API_KEY — fact-check database lookup disabled")
    if not settings.JWT_SECRET or settings.JWT_SECRET == "change-me-in-production":
        missing.append("JWT_SECRET is default/empty — set a strong secret before production")

    for w in missing:
        logger.warning("⚠️  %s", w)
    if missing:
        logger.warning("Configure missing values in .env for full functionality.")

    yield


app = FastAPI(
    title="ArtiProof API",
    description="Research Integrity Platform — source verification and academic integrity analysis",
    version="1.0.0",
    lifespan=lifespan,
)

cors_origins = list(settings.CORS_ORIGINS)
if settings.APP_URL and settings.APP_URL not in cors_origins:
    cors_origins.append(settings.APP_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(source_check_router)
app.include_router(researcher_router)
app.include_router(reports_router)
app.include_router(dashboard_router)
app.include_router(seed_router)


@app.get("/health")
async def health_check():
    """Simple liveness probe for local health-check clients."""
    return {"status": "healthy", "service": "artiproof-api", "version": "1.0.0"}


@app.get("/api/health")
async def detailed_health():
    """Detailed health + feature availability for the frontend."""
    return {
        "status": "ok",
        "service": "artiproof-api",
        "version": "1.0.0",
        "services": {
            "gemini": bool(settings.GEMINI_API_KEY),
            "google_factcheck": bool(settings.GOOGLE_FACTCHECK_API_KEY),
            "scopus": bool(settings.SCOPUS_API_KEY),
            "semantic_scholar": bool(settings.SEMANTIC_SCHOLAR_API_KEY),
        },
    }
