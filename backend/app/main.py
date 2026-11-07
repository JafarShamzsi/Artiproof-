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

app = FastAPI(
    title="ArtiProof API",
    description="Research Integrity Platform — source verification and academic integrity analysis",
    version="1.0.0",
)

# Build CORS origins — include configured origins + common patterns
cors_origins = list(settings.CORS_ORIGINS)
if settings.APP_URL and settings.APP_URL not in cors_origins:
    cors_origins.append(settings.APP_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # Allow all Vercel preview deploys
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
    return {"status": "healthy", "service": "artiproof-api", "version": "1.0.0"}
