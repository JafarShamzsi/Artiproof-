import json
import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete as sa_delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse


# ORCID format: 16 digits in 4 hyphenated groups, last digit may be X (mod-11 checksum)
ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")

from app.constants import MAX_BULK_RESEARCHERS, MAX_WATCHLIST
from app.database import get_db
from app.models.researcher import (
    CitationEdge,
    CoAuthorRelation,
    PublicationAnalysis,
    ResearcherProfile,
    ScrapedPublication,
)
from app.models.researcher_snapshot import ResearcherSnapshot
from app.models.user import User
from app.schemas.researcher import (
    DEFAULT_INTEGRITY_DISCLAIMER,
    BulkResearcherCreate,
    BulkResearcherResponse,
    CitationGraphResponse,
    PublicationAnalysisResponse,
    ResearcherAnalyzeRequest,
    ResearcherListItem,
    ResearcherListResponse,
    ResearcherProfileResponse,
    ResearcherSnapshotItem,
    WatchlistEntry,
)
from app.services.analysis_runs import queue_run
from app.utils.auth import (
    create_stream_ticket,
    decode_stream_ticket,
    get_current_user,
)
from app.utils.ownership import is_owner_or_org_admin
from app.utils.quota import assert_quota, enforce_quota
from app.utils.rate_limit import limiter, tier_aware_limit_for_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/researcher", tags=["Researcher Integrity"])


def _researcher_formula_version(record) -> str | None:
    for field in ("integrity_breakdown", "model_metadata"):
        data = getattr(record, field, None)
        if isinstance(data, dict) and isinstance(data.get("formula_version"), str):
            return data["formula_version"]
    return None


def _profile_to_response(profile: ResearcherProfile, publications=None) -> ResearcherProfileResponse:
    # Show the disclaimer whenever there's any analysis output to disclaim —
    # a profile in `pending` with no scores doesn't need the framing yet.
    has_findings = (
        profile.integrity_score is not None
        or profile.citation_ring_flags is not None
        or profile.self_citation_rate is not None
    )
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
        integrity_breakdown=profile.integrity_breakdown,
        model_metadata=profile.model_metadata,
        disclaimer=DEFAULT_INTEGRITY_DISCLAIMER if has_findings else None,
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
@limiter.limit(tier_aware_limit_for_key)
async def analyze_researcher(
    request: Request,
    data: ResearcherAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(enforce_quota("researcher_analyses")),
):
    """Submit a researcher for analysis."""
    user_id = current_user.id
    if not any([data.researcher_name, data.scopus_id, data.google_scholar_id, data.orcid]):
        raise HTTPException(status_code=400, detail="Provide at least one identifier")

    if data.orcid and not ORCID_PATTERN.match(data.orcid.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid ORCID format. Expected: 0000-0000-0000-0000 (final digit may be X)",
        )

    profile = ResearcherProfile(
        id=str(uuid.uuid4()),
        user_id=user_id,
        organization_id=current_user.organization_id,
        researcher_name=data.researcher_name or "Unknown",
        scopus_id=data.scopus_id,
        google_scholar_id=data.google_scholar_id,
        orcid=data.orcid,
        analysis_status="pending",
    )
    db.add(profile)
    await queue_run(db, "researcher", profile)
    await db.commit()
    await db.refresh(profile)

    # Best-effort enqueue. If Celery isn't installed/reachable the row stays
    # `pending` and the SSE stream will run the pipeline on first connect —
    # so the user-facing flow always works either way.
    try:
        from app.tasks import celery_app

        if celery_app is not None:
            celery_app.send_task("researcher.run_pipeline", args=[profile.id])
    except Exception:
        logger.exception("Prompt delivery failed; durable dispatcher will retry")

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
        select(func.count(ResearcherProfile.id)).where(
            ResearcherProfile.user_id == user_id, ResearcherProfile.deleted_at.is_(None)
        )
    )
    total = total_q.scalar() or 0

    result = await db.execute(
        select(ResearcherProfile)
        .where(ResearcherProfile.user_id == user_id, ResearcherProfile.deleted_at.is_(None))
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


# Batch poll for the bulk-mode UI. Declared BEFORE /{profile_id} so FastAPI
# matches the literal path first; otherwise GET /api/researcher/batch hits
# the catch-all and 404s with profile_id="batch".
@router.get("/batch", response_model=list[ResearcherListItem])
async def get_researcher_batch(
    ids: str = Query(..., description="Comma-separated profile ids"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Poll a researcher batch's status. Owned-only; missing ids omitted."""
    id_list = [s.strip() for s in ids.split(",") if s.strip()][:100]
    if not id_list:
        return []
    result = await db.execute(
        select(ResearcherProfile).where(
            ResearcherProfile.id.in_(id_list),
            ResearcherProfile.user_id == current_user.id,
            ResearcherProfile.deleted_at.is_(None),
        )
    )
    return [
        ResearcherListItem(
            id=p.id,
            researcher_name=p.researcher_name,
            institution=p.institution,
            integrity_score=p.integrity_score,
            analysis_status=p.analysis_status,
            created_at=p.created_at,
        )
        for p in result.scalars().all()
    ]


@router.get("/{profile_id}", response_model=ResearcherProfileResponse)
async def get_researcher_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full researcher profile with publications and integrity analysis.

    Requires authentication; only the user who created the profile may read it.
    """
    result = await db.execute(
        select(ResearcherProfile).where(
            ResearcherProfile.id == profile_id, ResearcherProfile.deleted_at.is_(None)
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Researcher profile not found")
    if not is_owner_or_org_admin(current_user, profile):
        raise HTTPException(status_code=403, detail="Not authorized to view this profile")

    # Load publications
    pubs_q = await db.execute(
        select(PublicationAnalysis)
        .where(PublicationAnalysis.researcher_profile_id == profile_id)
        .order_by(PublicationAnalysis.citation_count.desc())
    )
    publications = pubs_q.scalars().all()

    return _profile_to_response(profile, publications)


@router.post("/{profile_id}/stream-ticket")
async def issue_researcher_stream_ticket(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Issue a 60-second one-shot ticket the SSE endpoint will accept.

    Same pattern as ``/api/source-check/{id}/stream-ticket`` — bearer JWT
    here, narrow ticket bound to (user, profile_id) on the SSE call.
    """
    result = await db.execute(
        select(ResearcherProfile).where(
            ResearcherProfile.id == profile_id, ResearcherProfile.deleted_at.is_(None)
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Researcher profile not found")
    if not is_owner_or_org_admin(current_user, profile):
        raise HTTPException(status_code=403, detail="Not authorized to stream this profile")
    return {"ticket": create_stream_ticket(current_user.id, "researcher_profile", profile_id)}


@router.get("/{profile_id}/stream")
async def stream_researcher_analysis(
    profile_id: str,
    request: Request,
    ticket: str = Query(..., description="Stream ticket from /stream-ticket"),
    db: AsyncSession = Depends(get_db),
):
    """SSE endpoint — runs scraping first, then integrity analysis.

    Authenticated via a short-lived ticket (``?ticket=...``) issued by
    ``POST /{profile_id}/stream-ticket``. See source_check stream for the
    rationale; ticket is bound to (user, profile_id) and expires in 60s.
    """
    user_id = decode_stream_ticket(ticket, "researcher_profile", profile_id)
    result = await db.execute(
        select(ResearcherProfile).where(
            ResearcherProfile.id == profile_id, ResearcherProfile.deleted_at.is_(None)
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Researcher profile not found")
    # Stream tickets bind a specific user to a specific profile, so the
    # org-admin override (is_owner_or_org_admin) deliberately does NOT
    # apply here — a team admin who wants to stream a teammate's
    # analysis must issue their own ticket.
    if profile.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to stream this profile")

    from app.services.analysis_runs import observe_run, stream_cursor

    run_id = profile.current_run_id
    if not run_id:
        raise HTTPException(409, "This legacy analysis has no resumable run; submit a rerun")
    after = stream_cursor(request)
    await db.rollback()  # Return the request connection before the long-lived stream.
    return EventSourceResponse(observe_run(run_id, request, after=after))


@router.get("/{profile_id}/publications")
async def get_publications(
    profile_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Paginated list of analyzed publications."""
    profile_q = await db.execute(
        select(ResearcherProfile).where(
            ResearcherProfile.id == profile_id, ResearcherProfile.deleted_at.is_(None)
        )
    )
    profile = profile_q.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Researcher profile not found")
    if not is_owner_or_org_admin(current_user, profile):
        raise HTTPException(status_code=403, detail="Not authorized to view this profile")

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
async def get_citation_graph(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Citation network data for visualization."""
    result = await db.execute(
        select(ResearcherProfile).where(
            ResearcherProfile.id == profile_id, ResearcherProfile.deleted_at.is_(None)
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    if not is_owner_or_org_admin(current_user, profile):
        raise HTTPException(status_code=403, detail="Not authorized to view this profile")

    # Graph data is stored in citation_ring_flags
    ring_flags = profile.citation_ring_flags or {}
    graph = ring_flags.get("graph", {})

    return CitationGraphResponse(
        nodes=graph.get("nodes", []),
        edges=graph.get("edges", []),
    )


@router.delete("/{profile_id}", status_code=204)
async def delete_researcher_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a researcher profile. The row is retained for restore."""
    result = await db.execute(
        select(ResearcherProfile).where(
            ResearcherProfile.id == profile_id, ResearcherProfile.deleted_at.is_(None)
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Researcher profile not found")
    if not is_owner_or_org_admin(current_user, profile):
        raise HTTPException(status_code=403, detail="Not authorized to delete this profile")
    profile.deleted_at = datetime.now(timezone.utc)
    await db.commit()


# ─── Bulk submission ──────────────────────────────────────────────────────


@router.post("/bulk", response_model=BulkResearcherResponse, status_code=201)
@limiter.limit(tier_aware_limit_for_key)
async def create_bulk_researcher_analyses(
    request: Request,
    data: BulkResearcherCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit many researcher identifiers in one call.

    Each entry creates its own ResearcherProfile + Celery task. Frontend
    polls /batch?ids=… for progress. Same shape constraints as source-check
    bulk: max 50 entries, each must carry at least one identifier.
    """
    if not data.items:
        raise HTTPException(status_code=400, detail="items must be non-empty")
    if len(data.items) > MAX_BULK_RESEARCHERS:
        raise HTTPException(
            status_code=400,
            detail=f"At most {MAX_BULK_RESEARCHERS} researchers per batch",
        )

    # Bulk consumes N units up front. Same logic as source-check /bulk.
    await assert_quota(db, current_user, "researcher_analyses", units=len(data.items))

    batch_id = str(uuid.uuid4())[:8]
    created: list[ResearcherProfile] = []

    for item in data.items:
        if not any([item.researcher_name, item.scopus_id, item.google_scholar_id, item.orcid]):
            raise HTTPException(
                status_code=400,
                detail="Every batch item needs at least one identifier",
            )
        if item.orcid and not ORCID_PATTERN.match(item.orcid.strip()):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid ORCID format: {item.orcid}",
            )

        profile = ResearcherProfile(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            organization_id=current_user.organization_id,
            researcher_name=item.researcher_name or "Unknown",
            scopus_id=item.scopus_id,
            google_scholar_id=item.google_scholar_id,
            orcid=item.orcid,
            analysis_status="pending",
        )
        db.add(profile)
        await queue_run(db, "researcher", profile)

        created.append(profile)

    await db.commit()
    for p in created:
        await db.refresh(p)

    return BulkResearcherResponse(
        batch_id=batch_id,
        items=[
            ResearcherListItem(
                id=p.id,
                researcher_name=p.researcher_name,
                institution=p.institution,
                integrity_score=p.integrity_score,
                analysis_status=p.analysis_status,
                created_at=p.created_at,
            )
            for p in created
        ],
    )


# ─── Re-run (in-place; snapshots prior values) ────────────────────────────


@router.post("/{profile_id}/rerun", response_model=ResearcherProfileResponse, status_code=200)
@limiter.limit(tier_aware_limit_for_key)
async def rerun_researcher_analysis(
    request: Request,
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run the analysis on this researcher in place.

    The orchestrator's _save_results captures a ResearcherSnapshot of the
    current values before overwriting, so re-running preserves history.
    Profile id stays stable so any URLs / pins / watchlist entries pointing
    at it remain valid.

    This route resets analysis_status + scrape_status to 'pending' and
    queues a durable worker run. Frontend
    can either open the SSE stream to watch progress or poll the profile
    GET endpoint.
    """
    result = await db.execute(
        select(ResearcherProfile).where(
            ResearcherProfile.id == profile_id,
            ResearcherProfile.deleted_at.is_(None),
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Researcher profile not found")
    if not is_owner_or_org_admin(current_user, profile):
        raise HTTPException(status_code=403, detail="Not authorized to re-analyze this")

    await queue_run(db, "researcher", profile)

    # Reset for the next pipeline run. Don't clear the live metric columns
    # yet — _save_results needs them for the snapshot capture before it
    # overwrites them.
    profile.analysis_status = "pending"
    profile.scrape_status = "pending"

    # Drop scraped artifacts so the scraper rebuilds cleanly. The
    # PublicationAnalysis rows are dropped inside _save_results once the
    # snapshot is captured — leaving them in place here so the user can
    # still see the prior results while the rerun is in flight.
    await db.execute(
        sa_delete(ScrapedPublication).where(
            ScrapedPublication.researcher_profile_id == profile.id
        )
    )
    await db.execute(
        sa_delete(CitationEdge).where(CitationEdge.researcher_profile_id == profile.id)
    )
    await db.execute(
        sa_delete(CoAuthorRelation).where(CoAuthorRelation.researcher_profile_id == profile.id)
    )
    await db.commit()

    try:
        from app.tasks import celery_app

        if celery_app is not None:
            celery_app.send_task("researcher.run_pipeline", args=[profile.id])
    except Exception:
        logger.exception("Failed to enqueue researcher rerun pipeline")

    pubs_q = await db.execute(
        select(PublicationAnalysis)
        .where(PublicationAnalysis.researcher_profile_id == profile.id)
        .order_by(PublicationAnalysis.citation_count.desc())
    )
    return _profile_to_response(profile, pubs_q.scalars().all())


# ─── History snapshots ────────────────────────────────────────────────────


@router.get("/{profile_id}/snapshots", response_model=list[ResearcherSnapshotItem])
async def list_snapshots(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Historical snapshots for a researcher, newest first.

    Each row is a frozen capture of the prior analysis taken just before
    a re-run overwrote it. Use to plot integrity-score over time.
    """
    profile_q = await db.execute(
        select(ResearcherProfile).where(
            ResearcherProfile.id == profile_id,
            ResearcherProfile.deleted_at.is_(None),
        )
    )
    profile = profile_q.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Researcher profile not found")
    if not is_owner_or_org_admin(current_user, profile):
        raise HTTPException(status_code=403, detail="Not authorized")

    snap_q = await db.execute(
        select(ResearcherSnapshot)
        .where(ResearcherSnapshot.researcher_profile_id == profile_id)
        .order_by(ResearcherSnapshot.created_at.desc())
    )
    return [
        ResearcherSnapshotItem(
            id=s.id,
            captured_at=s.captured_at,
            created_at=s.created_at,
            official_h_index=s.official_h_index,
            official_citation_count=s.official_citation_count,
            adjusted_h_index=s.adjusted_h_index,
            adjusted_citation_count=s.adjusted_citation_count,
            integrity_score=s.integrity_score,
            self_citation_rate=s.self_citation_rate,
            topic_relevance_score=s.topic_relevance_score,
            total_publications=s.total_publications,
            formula_version=_researcher_formula_version(s),
        )
        for s in snap_q.scalars().all()
    ]


# ─── Watchlist ────────────────────────────────────────────────────────────


watchlist_router = APIRouter(prefix="/api/me/watchlist", tags=["Watchlist"])


@watchlist_router.get("", response_model=list[WatchlistEntry])
async def list_watchlist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Hydrated watchlist — current metrics + delta vs the latest snapshot.

    `integrity_score_delta` is present only for available scores with the
    same recorded formula version; unknown or different methods are not compared.
    """
    raw = current_user.watchlist or []
    if not isinstance(raw, list):
        return []

    by_id: dict[str, str | None] = {}  # researcher_id -> added_at iso
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        rid = entry.get("researcher_id")
        if isinstance(rid, str):
            by_id[rid] = entry.get("added_at")

    if not by_id:
        return []

    # Drop the strict `user_id == current_user.id` filter and re-apply
    # the org-admin-aware check in Python. Without this, an org admin
    # could add a teammate's researcher to their watchlist via the
    # `is_owner_or_org_admin` path in add_to_watchlist but never see
    # it come back through GET — the two endpoints had divergent
    # authorization rules.
    profiles_q = await db.execute(
        select(ResearcherProfile).where(
            ResearcherProfile.id.in_(list(by_id.keys())),
            ResearcherProfile.deleted_at.is_(None),
        )
    )
    profiles = {
        p.id: p
        for p in profiles_q.scalars().all()
        if is_owner_or_org_admin(current_user, p)
    }

    # Latest snapshot per profile — bulk fetch + group by researcher_profile_id.
    snaps_q = await db.execute(
        select(ResearcherSnapshot).where(
            ResearcherSnapshot.researcher_profile_id.in_(list(profiles.keys())),
        ).order_by(ResearcherSnapshot.created_at.desc())
    )
    latest_snap: dict[str, ResearcherSnapshot] = {}
    for s in snaps_q.scalars().all():
        # First (newest) wins because we ordered desc.
        latest_snap.setdefault(s.researcher_profile_id, s)

    out: list[WatchlistEntry] = []
    for rid, added_at_iso in by_id.items():
        p = profiles.get(rid)
        if p is None:
            continue
        snap = latest_snap.get(rid)
        delta = None
        current_version = _researcher_formula_version(p)
        if (snap is not None and current_version is not None
                and current_version == _researcher_formula_version(snap)
                and p.integrity_score is not None and snap.integrity_score is not None):
            delta = round(p.integrity_score - snap.integrity_score, 1)

        try:
            added_at = datetime.fromisoformat(added_at_iso) if added_at_iso else p.created_at
        except (TypeError, ValueError):
            added_at = p.created_at

        out.append(
            WatchlistEntry(
                researcher_id=p.id,
                researcher_name=p.researcher_name,
                institution=p.institution,
                integrity_score=p.integrity_score,
                self_citation_rate=p.self_citation_rate,
                integrity_score_delta=delta,
                last_analyzed_at=p.last_analyzed_at,
                last_snapshot_at=snap.created_at if snap else None,
                added_at=added_at,
            )
        )

    out.sort(key=lambda e: e.added_at, reverse=True)
    return out


@watchlist_router.post("/{researcher_id}", response_model=list[WatchlistEntry], status_code=201)
async def add_to_watchlist(
    researcher_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a researcher to the watchlist. Verifies ownership; idempotent
    (re-adding returns the current list); enforces MAX_WATCHLIST cap."""
    profile = await db.get(ResearcherProfile, researcher_id)
    if (
        profile is None
        or profile.deleted_at is not None
        or not is_owner_or_org_admin(current_user, profile)
    ):
        raise HTTPException(status_code=404, detail="Researcher profile not found")

    raw = list(current_user.watchlist or [])
    if any(
        isinstance(e, dict) and e.get("researcher_id") == researcher_id for e in raw
    ):
        return await list_watchlist(db=db, current_user=current_user)
    if len(raw) >= MAX_WATCHLIST:
        raise HTTPException(
            status_code=400,
            detail=f"Watchlist is full (max {MAX_WATCHLIST}). Remove someone first.",
        )

    raw.append({
        "researcher_id": researcher_id,
        "added_at": datetime.now(timezone.utc).isoformat(),
    })
    current_user.watchlist = raw
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)

    return await list_watchlist(db=db, current_user=current_user)


@watchlist_router.delete("/{researcher_id}", status_code=204)
async def remove_from_watchlist(
    researcher_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raw = list(current_user.watchlist or [])
    new_raw = [
        e
        for e in raw
        if not (isinstance(e, dict) and e.get("researcher_id") == researcher_id)
    ]
    if len(new_raw) == len(raw):
        raise HTTPException(status_code=404, detail="Not on watchlist")
    current_user.watchlist = new_raw or None
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
