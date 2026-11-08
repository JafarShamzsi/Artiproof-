import csv
import io
import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select, func
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.constants import MAX_FILE_SIZE_BYTES, MAX_FILE_SIZE_MB, MIN_FILE_SIZE_BYTES
from app.database import get_db
from app.models.source_check import SourceCheck, ClaimAnalysis, AIDetectionResult, CitationCheck
from app.models.user import User
from app.schemas.source_check import (
    BulkSourceCheckCreate,
    BulkSourceCheckResponse,
    ShareTokenResponse,
    SharedSourceCheckResponse,
    SourceCheckCreate,
    SourceCheckResponse,
    SourceCheckListItem,
    SourceCheckListResponse,
    ClaimAnalysisResponse,
    AIDetectionResponse,
    CitationCheckResponse,
)
from app.services.source_verification.orchestrator import SourceVerificationOrchestrator
from app.utils.auth import (
    create_stream_ticket,
    decode_stream_ticket,
    get_current_user,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/source-check", tags=["Source Verification"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "pdfs")


def _check_to_response(check: SourceCheck, claims=None, ai_detections=None, citations=None) -> SourceCheckResponse:
    return SourceCheckResponse(
        id=check.id,
        user_id=check.user_id,
        input_type=check.input_type,
        input_content=check.input_content,
        input_title=check.input_title,
        status=check.status,
        overall_credibility_score=check.overall_credibility_score,
        ai_content_percentage=check.ai_content_percentage,
        misinfo_claims_found=check.misinfo_claims_found,
        has_pdf=check.original_pdf_path is not None,
        has_annotated_pdf=check.annotated_pdf_path is not None,
        created_at=check.created_at,
        completed_at=check.completed_at,
        score_breakdown=check.score_breakdown,
        model_metadata=check.model_metadata,
        share_token=check.share_token,
        claims=[
            ClaimAnalysisResponse(
                id=c.id, claim_text=c.claim_text, verdict=c.verdict,
                confidence=c.confidence, explanation=c.explanation,
                true_version=c.true_version, sources=c.sources,
                origin_trace=c.origin_trace, position_in_text=c.position_in_text,
            )
            for c in (claims or [])
        ],
        ai_detections=[
            AIDetectionResponse(
                id=a.id, paragraph_index=a.paragraph_index,
                paragraph_text=a.paragraph_text, ai_probability=a.ai_probability,
                detection_method=a.detection_method,
            )
            for a in (ai_detections or [])
        ],
        citations=[
            CitationCheckResponse(
                id=ci.id, original_citation=ci.original_citation,
                citation_url=ci.citation_url, is_accessible=ci.is_accessible,
                is_retracted=ci.is_retracted, credibility_score=ci.credibility_score,
                issues=ci.issues, suggested_alternative=ci.suggested_alternative,
            )
            for ci in (citations or [])
        ],
    )


@router.post("/", response_model=SourceCheckResponse, status_code=201)
async def create_source_check(
    data: SourceCheckCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a new source check (URL or text)."""
    user_id = current_user.id
    orchestrator = SourceVerificationOrchestrator(db)
    check_id = await orchestrator.create_check(user_id, data.input_type, data.input_content)

    # Best-effort enqueue — SSE stream is still the primary trigger; this
    # ensures even abandoned tabs eventually run the pipeline.
    try:
        from app.tasks import celery_app

        if celery_app is not None:
            celery_app.send_task("source_check.run_pipeline", args=[check_id])
    except Exception:
        logger.exception("Failed to enqueue source-check pipeline (will run on SSE connect)")

    result = await db.execute(select(SourceCheck).where(SourceCheck.id == check_id))
    return _check_to_response(result.scalar_one())


@router.post("/upload", response_model=SourceCheckResponse, status_code=201)
async def upload_pdf_source_check(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a PDF document for source checking."""
    user_id = current_user.id

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large (max {MAX_FILE_SIZE_MB}MB)",
        )
    if len(contents) < MIN_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File is empty or too small to be a PDF")
    # Magic-byte check — reject anything not actually a PDF, regardless of extension
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="File is not a valid PDF")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{file_id}_{file.filename.replace(' ', '_')}"
    pdf_path = os.path.join(UPLOAD_DIR, safe_name)

    with open(pdf_path, "wb") as f:
        f.write(contents)

    orchestrator = SourceVerificationOrchestrator(db)
    check_id = await orchestrator.create_check(
        user_id=user_id,
        input_type="document",
        input_content=file.filename,
        original_pdf_path=pdf_path,
    )

    try:
        from app.tasks import celery_app

        if celery_app is not None:
            celery_app.send_task("source_check.run_pipeline", args=[check_id])
    except Exception:
        logger.exception("Failed to enqueue source-check pipeline (will run on SSE connect)")

    result = await db.execute(select(SourceCheck).where(SourceCheck.id == check_id))
    return _check_to_response(result.scalar_one())


SortKey = Literal[
    "created_at_desc", "created_at_asc", "score_desc", "score_asc"
]


@router.get("/", response_model=SourceCheckListResponse)
async def list_source_checks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: Optional[str] = Query(None, max_length=200),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    max_score: Optional[float] = Query(None, ge=0, le=100),
    status: Optional[str] = Query(None),  # pending|processing|completed|failed
    sort: SortKey = Query("created_at_desc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user's past source checks with optional search + filters.

    Filters:
      q: ILIKE substring on input_title + input_content
      min_score / max_score: filter by overall_credibility_score range
        (NULL scores excluded when either bound is set)
      status: exact match on the check_status enum
      sort: one of created_at_desc (default), created_at_asc, score_desc, score_asc
    """
    user_id = current_user.id

    where = [
        SourceCheck.user_id == user_id,
        SourceCheck.deleted_at.is_(None),
    ]
    if q:
        pattern = f"%{q.strip()}%"
        where.append(
            or_(
                SourceCheck.input_title.ilike(pattern),
                SourceCheck.input_content.ilike(pattern),
            )
        )
    if min_score is not None:
        where.append(SourceCheck.overall_credibility_score >= min_score)
    if max_score is not None:
        where.append(SourceCheck.overall_credibility_score <= max_score)
    if status is not None:
        where.append(SourceCheck.status == status)

    total_q = await db.execute(select(func.count(SourceCheck.id)).where(*where))
    total = total_q.scalar() or 0

    order_clauses: list = {
        "created_at_desc": [SourceCheck.created_at.desc()],
        "created_at_asc": [SourceCheck.created_at.asc()],
        "score_desc": [
            SourceCheck.overall_credibility_score.desc().nulls_last(),
            SourceCheck.created_at.desc(),
        ],
        "score_asc": [
            SourceCheck.overall_credibility_score.asc().nulls_last(),
            SourceCheck.created_at.desc(),
        ],
    }[sort]

    result = await db.execute(
        select(SourceCheck)
        .where(*where)
        .order_by(*order_clauses)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return SourceCheckListResponse(
        items=[
            SourceCheckListItem(
                id=c.id, input_type=c.input_type, input_title=c.input_title,
                status=c.status, overall_credibility_score=c.overall_credibility_score,
                ai_content_percentage=c.ai_content_percentage,
                misinfo_claims_found=c.misinfo_claims_found, created_at=c.created_at,
            )
            for c in result.scalars().all()
        ],
        total=total, page=page, page_size=page_size,
    )


@router.get("/batch", response_model=list[SourceCheckListItem])
async def get_batch(
    ids: str = Query(..., description="Comma-separated check ids"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch a batch's status — used by the bulk-mode UI to poll progress.
    Only returns checks owned by the current user; missing ids are silently
    omitted from the response."""
    id_list = [s.strip() for s in ids.split(",") if s.strip()][:100]
    if not id_list:
        return []
    result = await db.execute(
        select(SourceCheck).where(
            SourceCheck.id.in_(id_list),
            SourceCheck.user_id == current_user.id,
            SourceCheck.deleted_at.is_(None),
        )
    )
    return [
        SourceCheckListItem(
            id=c.id, input_type=c.input_type, input_title=c.input_title,
            status=c.status, overall_credibility_score=c.overall_credibility_score,
            ai_content_percentage=c.ai_content_percentage,
            misinfo_claims_found=c.misinfo_claims_found, created_at=c.created_at,
        )
        for c in result.scalars().all()
    ]


@router.get("/{check_id}", response_model=SourceCheckResponse)
async def get_source_check(
    check_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full source check results with claims, AI detection, citations.

    Requires authentication; only the user who created the check may read it.
    Public sharing happens via the share-token endpoint in the reports router,
    which intentionally does not require auth.
    """
    result = await db.execute(
        select(SourceCheck).where(
            SourceCheck.id == check_id, SourceCheck.deleted_at.is_(None)
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Source check not found")
    if check.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this check")

    claims_q = await db.execute(
        select(ClaimAnalysis).where(ClaimAnalysis.source_check_id == check_id).order_by(ClaimAnalysis.created_at)
    )
    ai_q = await db.execute(
        select(AIDetectionResult).where(AIDetectionResult.source_check_id == check_id).order_by(AIDetectionResult.paragraph_index)
    )
    cit_q = await db.execute(
        select(CitationCheck).where(CitationCheck.source_check_id == check_id).order_by(CitationCheck.created_at)
    )
    return _check_to_response(check, claims_q.scalars().all(), ai_q.scalars().all(), cit_q.scalars().all())


@router.post("/{check_id}/stream-ticket")
async def issue_source_check_stream_ticket(
    check_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Issue a 60-second one-shot ticket the SSE endpoint will accept.

    EventSource can't attach an Authorization header, so we authenticate
    out-of-band: the client POSTs here with their bearer JWT, we verify
    ownership, and hand back a narrow ticket bound to (user, check_id).
    """
    result = await db.execute(
        select(SourceCheck).where(
            SourceCheck.id == check_id, SourceCheck.deleted_at.is_(None)
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Source check not found")
    if check.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to stream this check")
    return {"ticket": create_stream_ticket(current_user.id, "source_check", check_id)}


@router.get("/{check_id}/stream")
async def stream_source_check(
    check_id: str,
    request: Request,
    ticket: str = Query(..., description="Stream ticket from /stream-ticket"),
    db: AsyncSession = Depends(get_db),
):
    """SSE endpoint — runs the pipeline and streams progress events.

    Authenticated via a short-lived ticket (``?ticket=...``) issued by
    ``POST /{check_id}/stream-ticket``. The browser ``EventSource`` API
    can't carry a Bearer header; the ticket is bound to (user, check_id)
    and expires in 60s, so a leaked ticket grants only this single stream.
    """
    user_id = decode_stream_ticket(ticket, "source_check", check_id)
    result = await db.execute(
        select(SourceCheck).where(
            SourceCheck.id == check_id, SourceCheck.deleted_at.is_(None)
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Source check not found")
    if check.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to stream this check")
    if check.status == "completed":
        raise HTTPException(status_code=400, detail="Check already completed")

    orchestrator = SourceVerificationOrchestrator(db)

    async def event_generator():
        try:
            async for event in orchestrator.run_pipeline_streaming(check_id):
                if await request.is_disconnected():
                    break
                yield {"event": event.get("step", "progress"), "data": json.dumps(event)}
        except Exception as e:
            logger.exception("SSE stream error")
            yield {"event": "error", "data": json.dumps({"step": "error", "status": "failed", "detail": str(e), "progress": 1.0})}

    return EventSourceResponse(event_generator())


@router.get("/{check_id}/pdf/original")
async def get_original_pdf(
    check_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve the original uploaded PDF."""
    result = await db.execute(
        select(SourceCheck).where(
            SourceCheck.id == check_id, SourceCheck.deleted_at.is_(None)
        )
    )
    check = result.scalar_one_or_none()
    if not check or not check.original_pdf_path:
        raise HTTPException(status_code=404, detail="Original PDF not found")
    if check.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this check")
    if not os.path.exists(check.original_pdf_path):
        raise HTTPException(status_code=404, detail="PDF file missing from disk")
    return FileResponse(check.original_pdf_path, media_type="application/pdf")


@router.get("/{check_id}/pdf/annotated")
async def get_annotated_pdf(
    check_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve the annotated PDF with highlights."""
    result = await db.execute(
        select(SourceCheck).where(
            SourceCheck.id == check_id, SourceCheck.deleted_at.is_(None)
        )
    )
    check = result.scalar_one_or_none()
    if not check or not check.annotated_pdf_path:
        raise HTTPException(status_code=404, detail="Annotated PDF not found")
    if check.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this check")
    if not os.path.exists(check.annotated_pdf_path):
        raise HTTPException(status_code=404, detail="Annotated PDF file missing from disk")
    return FileResponse(check.annotated_pdf_path, media_type="application/pdf")


@router.get("/{check_id}/position-map")
async def get_position_map(
    check_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the JSON mapping of findings to PDF coordinates."""
    result = await db.execute(
        select(SourceCheck).where(
            SourceCheck.id == check_id, SourceCheck.deleted_at.is_(None)
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Source check not found")
    if check.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this check")
    return JSONResponse(content=check.text_position_map or {"claims": {}, "ai_detections": {}, "citations": {}})


@router.delete("/{check_id}", status_code=204)
async def delete_source_check(
    check_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a source check.

    The row is marked with ``deleted_at`` rather than being removed so it can
    be restored. PDF files are intentionally retained for the same reason; a
    separate janitor job is responsible for hard-deleting old soft-deleted
    rows and their files.
    """
    result = await db.execute(
        select(SourceCheck).where(
            SourceCheck.id == check_id, SourceCheck.deleted_at.is_(None)
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Source check not found")
    if check.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this check")
    check.deleted_at = datetime.now(timezone.utc)
    await db.commit()


# ─── Bulk submission ──────────────────────────────────────────────────────


@router.post("/bulk", response_model=BulkSourceCheckResponse, status_code=201)
async def create_bulk_source_checks(
    data: BulkSourceCheckCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit many URL/text checks in one call. Each becomes its own
    SourceCheck row + Celery task. Frontend polls /batch?ids=… for progress.

    PDF bulk uploads have their own /bulk/upload endpoint because
    multipart/form-data with multiple files needs a different parser."""
    if not data.items:
        raise HTTPException(status_code=400, detail="items must be non-empty")
    if len(data.items) > 50:
        raise HTTPException(status_code=400, detail="At most 50 checks per batch")

    orchestrator = SourceVerificationOrchestrator(db)
    batch_id = str(uuid.uuid4())[:8]  # cosmetic — for the URL bar
    created: list[SourceCheck] = []

    for item in data.items:
        if item.input_type not in ("url", "text"):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported input_type {item.input_type!r}; use url or text",
            )
        check_id = await orchestrator.create_check(
            user_id=current_user.id,
            input_type=item.input_type,
            input_content=item.input_content,
        )
        # Best-effort enqueue per row
        try:
            from app.tasks import celery_app

            if celery_app is not None:
                celery_app.send_task("source_check.run_pipeline", args=[check_id])
        except Exception:
            logger.exception("Failed to enqueue bulk source-check pipeline")
        created.append((await db.execute(select(SourceCheck).where(SourceCheck.id == check_id))).scalar_one())

    return BulkSourceCheckResponse(
        batch_id=batch_id,
        items=[
            SourceCheckListItem(
                id=c.id, input_type=c.input_type, input_title=c.input_title,
                status=c.status, overall_credibility_score=c.overall_credibility_score,
                ai_content_percentage=c.ai_content_percentage,
                misinfo_claims_found=c.misinfo_claims_found, created_at=c.created_at,
            )
            for c in created
        ],
    )


# ─── Re-run ───────────────────────────────────────────────────────────────


@router.post("/{check_id}/rerun", response_model=SourceCheckResponse, status_code=201)
async def rerun_source_check(
    check_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clone an existing source check and run it through the pipeline again.

    Cloning (vs resetting) preserves the original analysis as history. The
    new check is owned by the current user, has the same input_type +
    input_content + original_pdf_path (if any), and starts in status=pending.
    """
    src_q = await db.execute(
        select(SourceCheck).where(
            SourceCheck.id == check_id, SourceCheck.deleted_at.is_(None)
        )
    )
    src = src_q.scalar_one_or_none()
    if src is None:
        raise HTTPException(status_code=404, detail="Source check not found")
    if src.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to re-check this")

    orchestrator = SourceVerificationOrchestrator(db)
    new_id = await orchestrator.create_check(
        user_id=current_user.id,
        input_type=src.input_type,
        input_content=src.input_content,
        original_pdf_path=src.original_pdf_path,
    )
    try:
        from app.tasks import celery_app

        if celery_app is not None:
            celery_app.send_task("source_check.run_pipeline", args=[new_id])
    except Exception:
        logger.exception("Failed to enqueue rerun source-check pipeline")

    result = await db.execute(select(SourceCheck).where(SourceCheck.id == new_id))
    return _check_to_response(result.scalar_one())


# ─── Share token ──────────────────────────────────────────────────────────


def _share_url_for(token: str) -> str:
    return f"{settings.APP_URL}/check/shared/{token}"


@router.post("/{check_id}/share-token", response_model=ShareTokenResponse)
async def issue_share_token(
    check_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Issue (or return existing) a public share token for this check.
    Idempotent — calling it twice returns the same token."""
    result = await db.execute(
        select(SourceCheck).where(
            SourceCheck.id == check_id, SourceCheck.deleted_at.is_(None)
        )
    )
    check = result.scalar_one_or_none()
    if check is None:
        raise HTTPException(status_code=404, detail="Source check not found")
    if check.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not check.share_token:
        check.share_token = secrets.token_urlsafe(32)
        check.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(check)

    return ShareTokenResponse(
        share_token=check.share_token, share_url=_share_url_for(check.share_token)
    )


@router.delete("/{check_id}/share-token", status_code=204)
async def revoke_share_token(
    check_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke the public share link. The next /share-token call generates
    a fresh one — old links 404."""
    result = await db.execute(
        select(SourceCheck).where(
            SourceCheck.id == check_id, SourceCheck.deleted_at.is_(None)
        )
    )
    check = result.scalar_one_or_none()
    if check is None:
        raise HTTPException(status_code=404, detail="Source check not found")
    if check.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    check.share_token = None
    check.updated_at = datetime.now(timezone.utc)
    await db.commit()


@router.get("/shared/{token}", response_model=SharedSourceCheckResponse)
async def get_shared_source_check(token: str, db: AsyncSession = Depends(get_db)):
    """Public read-only access via share token. No auth required.

    Redacts user_id and (for URL-type checks) input_content so the URL
    itself isn't disclosed beyond what the page already shows. Claims +
    AI detection + citations are returned in full — the analysis is the
    point of sharing."""
    result = await db.execute(
        select(SourceCheck).where(
            SourceCheck.share_token == token, SourceCheck.deleted_at.is_(None)
        )
    )
    check = result.scalar_one_or_none()
    if check is None:
        raise HTTPException(status_code=404, detail="Shared check not found")

    claims_q = await db.execute(
        select(ClaimAnalysis)
        .where(ClaimAnalysis.source_check_id == check.id)
        .order_by(ClaimAnalysis.created_at)
    )
    ai_q = await db.execute(
        select(AIDetectionResult)
        .where(AIDetectionResult.source_check_id == check.id)
        .order_by(AIDetectionResult.paragraph_index)
    )
    cit_q = await db.execute(
        select(CitationCheck)
        .where(CitationCheck.source_check_id == check.id)
        .order_by(CitationCheck.created_at)
    )

    return SharedSourceCheckResponse(
        id=check.id,
        input_type=check.input_type,
        input_title=check.input_title,
        status=check.status,
        overall_credibility_score=check.overall_credibility_score,
        ai_content_percentage=check.ai_content_percentage,
        misinfo_claims_found=check.misinfo_claims_found,
        has_pdf=check.original_pdf_path is not None,
        has_annotated_pdf=check.annotated_pdf_path is not None,
        created_at=check.created_at,
        completed_at=check.completed_at,
        score_breakdown=check.score_breakdown,
        claims=[
            ClaimAnalysisResponse(
                id=c.id, claim_text=c.claim_text, verdict=c.verdict,
                confidence=c.confidence, explanation=c.explanation,
                true_version=c.true_version, sources=c.sources,
                origin_trace=c.origin_trace, position_in_text=c.position_in_text,
            )
            for c in claims_q.scalars().all()
        ],
        ai_detections=[
            AIDetectionResponse(
                id=a.id, paragraph_index=a.paragraph_index,
                paragraph_text=a.paragraph_text, ai_probability=a.ai_probability,
                detection_method=a.detection_method,
            )
            for a in ai_q.scalars().all()
        ],
        citations=[
            CitationCheckResponse(
                id=ci.id, original_citation=ci.original_citation,
                citation_url=ci.citation_url, is_accessible=ci.is_accessible,
                is_retracted=ci.is_retracted, credibility_score=ci.credibility_score,
                issues=ci.issues, suggested_alternative=ci.suggested_alternative,
            )
            for ci in cit_q.scalars().all()
        ],
    )


# ─── Lightweight export ──────────────────────────────────────────────────


@router.get("/{check_id}/export")
async def export_source_check(
    check_id: str,
    format: Literal["json", "csv"] = Query("json"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lightweight export of a single check.

    JSON: same shape as GET /api/source-check/{id}.
    CSV: a flat row-per-finding sheet with check metadata in each row,
    suitable for spreadsheets / quick share over email. Each row carries:
    check_id, kind ("claim"|"ai_detection"|"citation"), title, score,
    plus kind-specific columns.

    PDF export uses the existing /api/reports/generate flow — link from
    the frontend, no special endpoint here.
    """
    result = await db.execute(
        select(SourceCheck).where(
            SourceCheck.id == check_id, SourceCheck.deleted_at.is_(None)
        )
    )
    check = result.scalar_one_or_none()
    if check is None:
        raise HTTPException(status_code=404, detail="Source check not found")
    if check.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    claims_q = await db.execute(
        select(ClaimAnalysis).where(ClaimAnalysis.source_check_id == check.id)
    )
    ai_q = await db.execute(
        select(AIDetectionResult).where(AIDetectionResult.source_check_id == check.id)
    )
    cit_q = await db.execute(
        select(CitationCheck).where(CitationCheck.source_check_id == check.id)
    )
    claims = claims_q.scalars().all()
    ai_results = ai_q.scalars().all()
    citations = cit_q.scalars().all()

    base_filename = f"artiproof-check-{check.id[:8]}"

    if format == "json":
        body = {
            "id": check.id,
            "input_type": check.input_type,
            "input_title": check.input_title,
            "input_content": check.input_content,
            "status": check.status,
            "overall_credibility_score": check.overall_credibility_score,
            "ai_content_percentage": check.ai_content_percentage,
            "misinfo_claims_found": check.misinfo_claims_found,
            "score_breakdown": check.score_breakdown,
            "model_metadata": check.model_metadata,
            "created_at": check.created_at.isoformat() if check.created_at else None,
            "completed_at": check.completed_at.isoformat() if check.completed_at else None,
            "claims": [
                {
                    "id": c.id, "claim_text": c.claim_text, "verdict": c.verdict,
                    "confidence": c.confidence, "explanation": c.explanation,
                    "true_version": c.true_version, "sources": c.sources,
                    "origin_trace": c.origin_trace,
                }
                for c in claims
            ],
            "ai_detections": [
                {
                    "id": a.id, "paragraph_index": a.paragraph_index,
                    "paragraph_text": a.paragraph_text,
                    "ai_probability": a.ai_probability,
                    "detection_method": a.detection_method,
                }
                for a in ai_results
            ],
            "citations": [
                {
                    "id": c.id, "original_citation": c.original_citation,
                    "citation_url": c.citation_url, "is_accessible": c.is_accessible,
                    "is_retracted": c.is_retracted,
                    "credibility_score": c.credibility_score, "issues": c.issues,
                    "suggested_alternative": c.suggested_alternative,
                }
                for c in citations
            ],
        }
        return Response(
            content=json.dumps(body, indent=2, default=str),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{base_filename}.json"'},
        )

    # CSV
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "check_id", "check_title", "kind", "title_or_text",
        "verdict_or_status", "score_or_probability", "details",
    ])
    for c in claims:
        writer.writerow([
            check.id, check.input_title or "",
            "claim", (c.claim_text or "")[:500],
            c.verdict, f"{c.confidence:.2f}",
            (c.explanation or "")[:500],
        ])
    for a in ai_results:
        writer.writerow([
            check.id, check.input_title or "",
            "ai_detection", (a.paragraph_text or "")[:500],
            a.detection_method, f"{a.ai_probability:.2f}",
            f"paragraph #{a.paragraph_index}",
        ])
    for c in citations:
        status = (
            "retracted" if c.is_retracted
            else ("inaccessible" if not c.is_accessible else "ok")
        )
        writer.writerow([
            check.id, check.input_title or "",
            "citation", (c.original_citation or "")[:500],
            status,
            f"{(c.credibility_score or 0):.0f}",
            c.citation_url or "",
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{base_filename}.csv"'},
    )
