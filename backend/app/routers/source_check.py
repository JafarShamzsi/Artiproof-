import json
import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.models.source_check import SourceCheck, ClaimAnalysis, AIDetectionResult, CitationCheck
from app.models.user import User
from app.schemas.source_check import (
    SourceCheckCreate,
    SourceCheckResponse,
    SourceCheckListItem,
    SourceCheckListResponse,
    ClaimAnalysisResponse,
    AIDetectionResponse,
    CitationCheckResponse,
)
from app.services.source_verification.orchestrator import SourceVerificationOrchestrator
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/source-check", tags=["source-check"])

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

    # Save uploaded PDF
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{file_id}_{file.filename.replace(' ', '_')}"
    pdf_path = os.path.join(UPLOAD_DIR, safe_name)

    contents = await file.read()
    if len(contents) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    with open(pdf_path, "wb") as f:
        f.write(contents)

    orchestrator = SourceVerificationOrchestrator(db)
    check_id = await orchestrator.create_check(
        user_id=user_id,
        input_type="document",
        input_content=file.filename,
        original_pdf_path=pdf_path,
    )

    result = await db.execute(select(SourceCheck).where(SourceCheck.id == check_id))
    return _check_to_response(result.scalar_one())


@router.get("/", response_model=SourceCheckListResponse)
async def list_source_checks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user's past source checks (paginated)."""
    user_id = current_user.id
    total_q = await db.execute(
        select(func.count(SourceCheck.id)).where(SourceCheck.user_id == user_id)
    )
    total = total_q.scalar() or 0

    result = await db.execute(
        select(SourceCheck)
        .where(SourceCheck.user_id == user_id)
        .order_by(SourceCheck.created_at.desc())
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


@router.get("/{check_id}", response_model=SourceCheckResponse)
async def get_source_check(check_id: str, db: AsyncSession = Depends(get_db)):
    """Get full source check results with claims, AI detection, citations."""
    result = await db.execute(select(SourceCheck).where(SourceCheck.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Source check not found")

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


@router.get("/{check_id}/stream")
async def stream_source_check(check_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """SSE endpoint — runs the pipeline and streams progress events."""
    result = await db.execute(select(SourceCheck).where(SourceCheck.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Source check not found")
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
async def get_original_pdf(check_id: str, db: AsyncSession = Depends(get_db)):
    """Serve the original uploaded PDF."""
    result = await db.execute(select(SourceCheck).where(SourceCheck.id == check_id))
    check = result.scalar_one_or_none()
    if not check or not check.original_pdf_path:
        raise HTTPException(status_code=404, detail="Original PDF not found")
    if not os.path.exists(check.original_pdf_path):
        raise HTTPException(status_code=404, detail="PDF file missing from disk")
    return FileResponse(check.original_pdf_path, media_type="application/pdf")


@router.get("/{check_id}/pdf/annotated")
async def get_annotated_pdf(check_id: str, db: AsyncSession = Depends(get_db)):
    """Serve the annotated PDF with highlights."""
    result = await db.execute(select(SourceCheck).where(SourceCheck.id == check_id))
    check = result.scalar_one_or_none()
    if not check or not check.annotated_pdf_path:
        raise HTTPException(status_code=404, detail="Annotated PDF not found")
    if not os.path.exists(check.annotated_pdf_path):
        raise HTTPException(status_code=404, detail="Annotated PDF file missing from disk")
    return FileResponse(check.annotated_pdf_path, media_type="application/pdf")


@router.get("/{check_id}/position-map")
async def get_position_map(check_id: str, db: AsyncSession = Depends(get_db)):
    """Return the JSON mapping of findings to PDF coordinates."""
    result = await db.execute(select(SourceCheck).where(SourceCheck.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Source check not found")
    return JSONResponse(content=check.text_position_map or {"claims": {}, "ai_detections": {}, "citations": {}})


@router.delete("/{check_id}", status_code=204)
async def delete_source_check(check_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a source check and all related data."""
    result = await db.execute(select(SourceCheck).where(SourceCheck.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Source check not found")
    # Clean up PDF files
    for path in [check.original_pdf_path, check.annotated_pdf_path]:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    await db.delete(check)
    await db.commit()
