import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.models.researcher import ResearcherProfile, PublicationAnalysis
from app.models.user import User
from app.schemas.researcher import (
    ResearcherAnalyzeRequest,
    ResearcherProfileResponse,
    ResearcherListItem,
    ResearcherListResponse,
    PublicationAnalysisResponse,
    CitationGraphResponse,
)
from app.services.academic_integrity.orchestrator import AcademicIntegrityOrchestrator
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/researcher", tags=["researcher"])


def _profile_to_response(profile: ResearcherProfile, publications=None) -> ResearcherProfileResponse:
    return ResearcherProfileResponse(
        id=profile.id,
        researcher_name=profile.researcher_name,
        scopus_id=profile.scopus_id,
        google_scholar_id=profile.google_scholar_id,
        orcid=profile.orcid,
        institution=profile.institution,
        official_h_index=profile.official_h_index,
        official_citation_count=profile.official_citation_count,
        adjusted_h_index=profile.adjusted_h_index,
        adjusted_citation_count=profile.adjusted_citation_count,
        integrity_score=profile.integrity_score,
        self_citation_rate=profile.self_citation_rate,
        citation_ring_flags=profile.citation_ring_flags,
        topic_relevance_score=profile.topic_relevance_score,
        analysis_status=profile.analysis_status,
        last_analyzed_at=profile.last_analyzed_at,
        created_at=profile.created_at,
        publications=[
            PublicationAnalysisResponse(
                id=p.id,
                title=p.title,
                journal=p.journal,
                year=p.year,
                doi=p.doi,
                citation_count=p.citation_count,
                suspicious_citations=p.suspicious_citations,
                topic_match_score=p.topic_match_score,
                is_self_cited_heavily=p.is_self_cited_heavily,
                flags=p.flags,
            )
            for p in (publications or [])
        ],
    )


@router.post("/analyze", response_model=ResearcherProfileResponse, status_code=201)
async def analyze_researcher(
    data: ResearcherAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a researcher for analysis."""
    user_id = current_user.id
    if not any([data.researcher_name, data.scopus_id, data.google_scholar_id, data.orcid]):
        raise HTTPException(status_code=400, detail="Provide at least one identifier")

    profile = ResearcherProfile(
        user_id=user_id,
        researcher_name=data.researcher_name or "Unknown",
        scopus_id=data.scopus_id,
        google_scholar_id=data.google_scholar_id,
        orcid=data.orcid,
        analysis_status="pending",
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return _profile_to_response(profile)


@router.get("/", response_model=ResearcherListResponse)
async def list_researcher_analyses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user's past researcher analyses (paginated)."""
    user_id = current_user.id
    total_q = await db.execute(
        select(func.count(ResearcherProfile.id)).where(ResearcherProfile.user_id == user_id)
    )
    total = total_q.scalar() or 0

    result = await db.execute(
        select(ResearcherProfile)
        .where(ResearcherProfile.user_id == user_id)
        .order_by(ResearcherProfile.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    profiles = result.scalars().all()

    return ResearcherListResponse(
        items=[
            ResearcherListItem(
                id=p.id,
                researcher_name=p.researcher_name,
                institution=p.institution,
                integrity_score=p.integrity_score,
                analysis_status=p.analysis_status,
                created_at=p.created_at,
            )
            for p in profiles
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{profile_id}", response_model=ResearcherProfileResponse)
async def get_researcher_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    """Get full researcher profile with publications and integrity analysis."""
    result = await db.execute(
        select(ResearcherProfile).where(ResearcherProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Researcher profile not found")

    # Load publications
    pubs_q = await db.execute(
        select(PublicationAnalysis)
        .where(PublicationAnalysis.researcher_profile_id == profile_id)
        .order_by(PublicationAnalysis.citation_count.desc())
    )
    publications = pubs_q.scalars().all()

    return _profile_to_response(profile, publications)


@router.get("/{profile_id}/stream")
async def stream_researcher_analysis(profile_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """SSE endpoint — runs scraping first, then integrity analysis."""
    result = await db.execute(
        select(ResearcherProfile).where(ResearcherProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Researcher profile not found")

    if profile.analysis_status == "completed":
        raise HTTPException(status_code=400, detail="Analysis already completed")

    from app.services.scrapers.scrape_orchestrator import ScrapeOrchestrator

    scrape_orchestrator = ScrapeOrchestrator(db)
    analysis_orchestrator = AcademicIntegrityOrchestrator(db)

    async def event_generator():
        try:
            # Phase 1: Scrape data from external APIs
            async for event in scrape_orchestrator.run_scraping(profile_id):
                if await request.is_disconnected():
                    return
                # Scale scraping progress to 0-50%
                event["progress"] = event["progress"] * 0.5
                yield {"event": event.get("step", "progress"), "data": json.dumps(event)}
                if event.get("status") == "failed":
                    return

            # Phase 2: Run integrity analysis on scraped data
            async for event in analysis_orchestrator.run_pipeline_streaming(profile_id):
                if await request.is_disconnected():
                    return
                # Scale analysis progress to 50-100%
                event["progress"] = 0.5 + event["progress"] * 0.5
                yield {"event": event.get("step", "progress"), "data": json.dumps(event)}

        except Exception as e:
            logger.exception("SSE stream error")
            yield {"event": "error", "data": json.dumps({"step": "error", "status": "failed", "detail": str(e), "progress": 1.0})}

    return EventSourceResponse(event_generator())


@router.get("/{profile_id}/publications")
async def get_publications(
    profile_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of analyzed publications."""
    total_q = await db.execute(
        select(func.count(PublicationAnalysis.id))
        .where(PublicationAnalysis.researcher_profile_id == profile_id)
    )
    total = total_q.scalar() or 0

    result = await db.execute(
        select(PublicationAnalysis)
        .where(PublicationAnalysis.researcher_profile_id == profile_id)
        .order_by(PublicationAnalysis.citation_count.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    pubs = result.scalars().all()

    return {
        "items": [
            PublicationAnalysisResponse(
                id=p.id, title=p.title, journal=p.journal, year=p.year,
                doi=p.doi, citation_count=p.citation_count,
                suspicious_citations=p.suspicious_citations,
                topic_match_score=p.topic_match_score,
                is_self_cited_heavily=p.is_self_cited_heavily, flags=p.flags,
            )
            for p in pubs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{profile_id}/citation-graph", response_model=CitationGraphResponse)
async def get_citation_graph(profile_id: str, db: AsyncSession = Depends(get_db)):
    """Citation network data for visualization."""
    result = await db.execute(
        select(ResearcherProfile).where(ResearcherProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Graph data is stored in citation_ring_flags
    ring_flags = profile.citation_ring_flags or {}
    graph = ring_flags.get("graph", {})

    return CitationGraphResponse(
        nodes=graph.get("nodes", []),
        edges=graph.get("edges", []),
    )
