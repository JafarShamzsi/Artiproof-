import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.report import Report
from app.models.source_check import SourceCheck, ClaimAnalysis, AIDetectionResult, CitationCheck
from app.models.researcher import ResearcherProfile, PublicationAnalysis
from app.models.user import User
from app.schemas.report import ReportGenerateRequest, ReportResponse, ReportListResponse
from app.utils.auth import get_current_user
from app.services.report_engine.narrative_generator import (
    generate_source_check_narrative,
    generate_researcher_narrative,
)
from app.services.report_engine.html_template import (
    render_source_check_report,
    render_researcher_report,
)
from app.services.report_engine.pdf_generator import html_to_pdf, save_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])


def _report_response(r: Report) -> ReportResponse:
    return ReportResponse(
        id=r.id, user_id=r.user_id,
        source_check_id=r.source_check_id,
        researcher_profile_id=r.researcher_profile_id,
        report_type=r.report_type, title=r.title,
        summary=r.summary, pdf_path=r.pdf_path,
        share_token=r.share_token, created_at=r.created_at,
    )


@router.post("/generate", response_model=ReportResponse, status_code=201)
async def generate_report(
    data: ReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate PDF report for a source check or researcher analysis."""
    user_id = current_user.id

    if data.source_check_id:
        # Source verification report
        result = await db.execute(select(SourceCheck).where(SourceCheck.id == data.source_check_id))
        check = result.scalar_one_or_none()
        if not check:
            raise HTTPException(status_code=404, detail="Source check not found")

        # Load related data
        claims_q = await db.execute(select(ClaimAnalysis).where(ClaimAnalysis.source_check_id == check.id))
        ai_q = await db.execute(select(AIDetectionResult).where(AIDetectionResult.source_check_id == check.id))
        cit_q = await db.execute(select(CitationCheck).where(CitationCheck.source_check_id == check.id))

        check_data = {
            "input_title": check.input_title,
            "input_type": check.input_type,
            "overall_credibility_score": check.overall_credibility_score or 0,
            "ai_content_percentage": check.ai_content_percentage or 0,
            "misinfo_claims_found": check.misinfo_claims_found or 0,
            "claims": [
                {"claim_text": c.claim_text, "verdict": c.verdict, "confidence": c.confidence,
                 "explanation": c.explanation, "true_version": c.true_version}
                for c in claims_q.scalars().all()
            ],
            "citations": [
                {"original_citation": c.original_citation, "is_retracted": c.is_retracted,
                 "is_accessible": c.is_accessible, "credibility_score": c.credibility_score or 0}
                for c in cit_q.scalars().all()
            ],
        }

        narrative = await generate_source_check_narrative(check_data)
        html = render_source_check_report(check_data, narrative)
        title = f"Source Verification: {check.input_title or 'Report'}"
        report_type = "source_verification"
        source_check_id = check.id
        researcher_profile_id = None

    elif data.researcher_profile_id:
        # Researcher integrity report
        result = await db.execute(
            select(ResearcherProfile).where(ResearcherProfile.id == data.researcher_profile_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Researcher profile not found")

        pubs_q = await db.execute(
            select(PublicationAnalysis)
            .where(PublicationAnalysis.researcher_profile_id == profile.id)
            .order_by(PublicationAnalysis.citation_count.desc())
        )

        profile_data = {
            "researcher_name": profile.researcher_name,
            "institution": profile.institution,
            "official_h_index": profile.official_h_index,
            "adjusted_h_index": profile.adjusted_h_index,
            "official_citation_count": profile.official_citation_count,
            "adjusted_citation_count": profile.adjusted_citation_count,
            "integrity_score": profile.integrity_score,
            "self_citation_rate": profile.self_citation_rate,
            "citation_ring_flags": profile.citation_ring_flags,
            "publications": [
                {"title": p.title, "journal": p.journal, "year": p.year,
                 "citation_count": p.citation_count, "topic_match_score": p.topic_match_score}
                for p in pubs_q.scalars().all()
            ],
        }

        narrative = await generate_researcher_narrative(profile_data)
        html = render_researcher_report(profile_data, narrative)
        title = f"Researcher Integrity: {profile.researcher_name}"
        report_type = "researcher_integrity"
        source_check_id = None
        researcher_profile_id = profile.id

    else:
        raise HTTPException(status_code=400, detail="Provide source_check_id or researcher_profile_id")

    # Generate PDF
    try:
        pdf_bytes = html_to_pdf(html)
        pdf_path = save_pdf(pdf_bytes)
    except Exception:
        logger.exception("PDF generation failed")
        pdf_path = None

    report = Report(
        user_id=user_id,
        source_check_id=source_check_id,
        researcher_profile_id=researcher_profile_id,
        report_type=report_type,
        title=title,
        summary=narrative[:2000],
        pdf_path=pdf_path,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return _report_response(report)


@router.get("/", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user's reports."""
    user_id = current_user.id
    total_q = await db.execute(select(func.count(Report.id)).where(Report.user_id == user_id))
    total = total_q.scalar() or 0

    result = await db.execute(
        select(Report).where(Report.user_id == user_id)
        .order_by(Report.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )

    return ReportListResponse(
        items=[_report_response(r) for r in result.scalars().all()],
        total=total, page=page, page_size=page_size,
    )


@router.get("/shared/{share_token}", response_model=ReportResponse)
async def get_shared_report(share_token: str, db: AsyncSession = Depends(get_db)):
    """Public report access (no auth required)."""
    result = await db.execute(select(Report).where(Report.share_token == share_token))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_response(report)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: str, db: AsyncSession = Depends(get_db)):
    """Get report details."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_response(report)


async def _regenerate_report_pdf(report: Report, db: AsyncSession) -> bytes:
    """Rebuild the PDF from the report's related data when the cached file is missing.

    Uses the stored summary as the narrative — no Gemini call needed.
    """
    narrative = report.summary or ""

    if report.source_check_id:
        sc_result = await db.execute(select(SourceCheck).where(SourceCheck.id == report.source_check_id))
        check = sc_result.scalar_one_or_none()
        if not check:
            raise HTTPException(status_code=410, detail="Underlying source check no longer exists")

        claims_q = await db.execute(select(ClaimAnalysis).where(ClaimAnalysis.source_check_id == check.id))
        cit_q = await db.execute(select(CitationCheck).where(CitationCheck.source_check_id == check.id))

        check_data = {
            "input_title": check.input_title,
            "input_type": check.input_type,
            "overall_credibility_score": check.overall_credibility_score or 0,
            "ai_content_percentage": check.ai_content_percentage or 0,
            "misinfo_claims_found": check.misinfo_claims_found or 0,
            "claims": [
                {"claim_text": c.claim_text, "verdict": c.verdict, "confidence": c.confidence,
                 "explanation": c.explanation, "true_version": c.true_version}
                for c in claims_q.scalars().all()
            ],
            "citations": [
                {"original_citation": c.original_citation, "is_retracted": c.is_retracted,
                 "is_accessible": c.is_accessible, "credibility_score": c.credibility_score or 0}
                for c in cit_q.scalars().all()
            ],
        }
        html = render_source_check_report(check_data, narrative)

    elif report.researcher_profile_id:
        rp_result = await db.execute(
            select(ResearcherProfile).where(ResearcherProfile.id == report.researcher_profile_id)
        )
        profile = rp_result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=410, detail="Underlying researcher profile no longer exists")

        pubs_q = await db.execute(
            select(PublicationAnalysis)
            .where(PublicationAnalysis.researcher_profile_id == profile.id)
            .order_by(PublicationAnalysis.citation_count.desc())
        )
        profile_data = {
            "researcher_name": profile.researcher_name,
            "institution": profile.institution,
            "official_h_index": profile.official_h_index,
            "adjusted_h_index": profile.adjusted_h_index,
            "official_citation_count": profile.official_citation_count,
            "adjusted_citation_count": profile.adjusted_citation_count,
            "integrity_score": profile.integrity_score,
            "self_citation_rate": profile.self_citation_rate,
            "citation_ring_flags": profile.citation_ring_flags,
            "publications": [
                {"title": p.title, "journal": p.journal, "year": p.year,
                 "citation_count": p.citation_count, "topic_match_score": p.topic_match_score}
                for p in pubs_q.scalars().all()
            ],
        }
        html = render_researcher_report(profile_data, narrative)

    else:
        raise HTTPException(status_code=500, detail="Report has no underlying source or researcher record")

    return html_to_pdf(html)


@router.get("/{report_id}/download")
async def download_report(report_id: str, db: AsyncSession = Depends(get_db)):
    """Download PDF report. Regenerates on the fly if the cached file is missing —
    Local generated reports may not yet have a cached artifact."""
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if report.pdf_path and os.path.exists(report.pdf_path):
        with open(report.pdf_path, "rb") as f:
            pdf_bytes = f.read()
    else:
        try:
            pdf_bytes = await _regenerate_report_pdf(report, db)
        except HTTPException:
            raise
        except Exception:
            logger.exception("PDF regeneration failed for report %s", report.id)
            raise HTTPException(status_code=500, detail="PDF generation failed")

        # Best-effort cache the freshly rendered PDF. Filesystem may be read-only
        # or ephemeral; failure here is fine — we already have the bytes.
        try:
            from app.services.report_engine.pdf_generator import save_pdf
            new_path = save_pdf(pdf_bytes)
            report.pdf_path = new_path
            await db.commit()
        except Exception:
            logger.debug("Could not persist regenerated PDF path (ephemeral fs?)")

    filename = f"artiproof-report-{report.id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
