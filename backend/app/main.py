from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import scan, education, community

app = FastAPI(
    title="CivicGuards API",
    description="AI-powered misinformation detection and media literacy platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan.router, prefix="/api/v1/scan", tags=["scan"])
app.include_router(education.router, prefix="/api/v1/education", tags=["education"])
app.include_router(community.router, prefix="/api/v1/community", tags=["community"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "civicguards-api", "version": "0.1.0"}
