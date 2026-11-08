import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.organization import Organization
from app.models.report import Report
from app.models.researcher import PublicationAnalysis, ResearcherProfile
from app.models.source_check import (
    AIDetectionResult,
    CitationCheck,
    ClaimAnalysis,
    SourceCheck,
)
from app.models.user import User
from app.schemas.report import (
    ReportAnnotationsUpdate,
    ReportGenerateRequest,
    ReportListResponse,
    ReportResponse,
)
from app.services.report_engine.html_template import (
    render_comparison_report,
    render_executive_summary_report,
    render_institutional_audit_report,
    render_researcher_report,
    render_source_check_report,
)
from app.services.report_engine.narrative_generator import (
    generate_researcher_narrative,
    generate_source_check_narrative,
)
from app.services.report_engine.pdf_generator import html_to_pdf, save_pdf
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["Reports"])


# ─── Helpers ──────────────────────────────────────────────────────────────


async def _branding_for_user(user: User, db: AsyncSession) -> dict | None:
    """Resolve white-label branding for a user. Free/pro tier returns None
    (renderer falls back to ArtiProof default). Team tier with no org also
    returns None — branding only applies when the user is in an org."""
    if user.tier != "team" or not user.organization_id:
        return None
    result = await db.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    org = result.scalar_one_or_none()
    if not org or not (org.logo_url or org.primary_color):
        return None
    return {
        "name": org.name,
        "logo_url": org.logo_url,
        "primary_color": org.primary_color,
        "tagline": "Research Integrity Platform",
    }


async def _load_check_data(check: SourceCheck, db: AsyncSession) -> dict:
    """Load a SourceCheck plus its claims/citations into the dict shape the
    renderer expects. Centralized so /generate and /regenerate share it."""
    claims_q = await db.execute(
        select(ClaimAnalysis).where(ClaimAnalysis.source_check_id == check.id)
    )
    cit_q = await db.execute(
        select(CitationCheck).where(CitationCheck.source_check_id == check.id)
    )
    return {
        "input_title": check.input_title,
        "input_type": check.input_type,
        "overall_credibility_score": check.overall_credibility_score or 0,
        "ai_content_percentage": check.ai_content_percentage or 0,
        "misinfo_claims_found": check.misinfo_claims_found or 0,
        "claims": [
            {
                "claim_text": c.claim_text,
                "verdict": c.verdict,
                "confidence": c.confidence,
                "explanation": c.explanation,
                "true_version": c.true_version,
            }
            for c in claims_q.scalars().all()
        ],
        "citations": [
            {
                "original_citation": c.original_citation,
                "is_retracted": c.is_retracted,
                "is_accessible": c.is_accessible,
                "credibility_score": c.credibility_score or 0,
            }
            for c in cit_q.scalars().all()
        ],
    }


async def _load_researcher_data(
    profile: ResearcherProfile, db: AsyncSession
) -> dict:
    pubs_q = await db.execute(
        select(PublicationAnalysis)
        .where(PublicationAnalysis.researcher_profile_id == profile.id)
        .order_by(PublicationAnalysis.citation_count.desc())
    )
    return {
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
            {
                "title": p.title,
                "journal": p.journal,
                "year": p.year,
                "citation_count": p.citation_count,
                "topic_match_score": p.topic_match_score,
            }
            for p in pubs_q.scalars().all()
        ],
    }


def _report_response(r: Report) -> ReportResponse:
    # getattr fallbacks let test fixtures stub Report with SimpleNamespace
    # without re-listing every column. New columns added to Report are
    # always optional in the response schema, so this stays safe.
    return ReportResponse(
        id=r.id,
        user_id=r.user_id,
        source_check_id=r.source_check_id,
        researcher_profile_id=r.researcher_profile_id,
        report_type=r.report_type,
        template=getattr(r, "template", None) or "full",
        title=r.title,
        summary=r.summary,
        pdf_path=r.pdf_path,
        share_token=r.share_token,
        annotations=getattr(r, "annotations", None),
        source_check_ids=getattr(r, "source_check_ids", None),
        researcher_profile_ids=getattr(r, "researcher_profile_ids", None),
        created_at=r.created_at,
    )


# ─── Generate ─────────────────────────────────────────────────────────────


@router.post("/generate", response_model=ReportResponse, status_code=201)
async def generate_report(
    data: ReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a PDF report.

    Templates:
    - `full` (default): single source check or single researcher profile.
    - `executive_summary`: 1-page condensed; same single inputs as `full`.
    - `comparison`: requires `source_check_ids` (≥2). Side-by-side scoreboard.
    - `institutional_audit`: requires `researcher_profile_ids` (≥2).

    Every supplied id is ownership-checked against the current user before
    rendering.
    """
    user_id = current_user.id
    branding = await _branding_for_user(current_user, db)
    template = data.template

    # Validate template/input combinations
    if template == "comparison":
        if not data.source_check_ids or len(data.source_check_ids) < 2:
            raise HTTPException(
                status_code=400,
                detail="comparison template requires source_check_ids (at least 2)",
            )
    elif template == "institutional_audit":
        if not data.researcher_profile_ids or len(data.researcher_profile_ids) < 2:
            raise HTTPException(
                status_code=400,
                detail="institutional_audit template requires researcher_profile_ids (at least 2)",
            )
    else:
        # full / executive_summary
        if not data.source_check_id and not data.researcher_profile_id:
            raise HTTPException(
                status_code=400,
                detail="Provide source_check_id or researcher_profile_id",
            )

    # ─── Comparison: multi source check ───────────────────────────────
    if template == "comparison":
        if len(data.source_check_ids) > 10:
            raise HTTPException(status_code=400, detail="Up to 10 sources per comparison")
        result = await db.execute(
            select(SourceCheck).where(SourceCheck.id.in_(data.source_check_ids))
        )
        checks = list(result.scalars().all())
        if len(checks) != len(set(data.source_check_ids)):
            raise HTTPException(status_code=404, detail="One or more source checks not found")
        for c in checks:
            if c.user_id != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to use one of the source checks")
        items = [await _load_check_data(c, db) for c in checks]
        narrative = ""
        html = render_comparison_report(items, branding=branding)
        title = f"Source Comparison ({len(items)} sources)"
        report_type = "comparison"
        source_check_id: str | None = None
        researcher_profile_id: str | None = None
        source_check_ids = data.source_check_ids
        researcher_profile_ids = None

    # ─── Institutional audit: multi researcher ────────────────────────
    elif template == "institutional_audit":
        if len(data.researcher_profile_ids) > 25:
            raise HTTPException(status_code=400, detail="Up to 25 researchers per audit")
        result = await db.execute(
            select(ResearcherProfile).where(
                ResearcherProfile.id.in_(data.researcher_profile_ids)
            )
        )
        profiles = list(result.scalars().all())
        if len(profiles) != len(set(data.researcher_profile_ids)):
            raise HTTPException(status_code=404, detail="One or more researcher profiles not found")
        for p in profiles:
            if p.user_id != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to use one of the researcher profiles",
                )
        items = [await _load_researcher_data(p, db) for p in profiles]
        narrative = ""
        html = render_institutional_audit_report(items, branding=branding)
        title = f"Institutional Audit ({len(items)} researchers)"
        report_type = "institutional_audit"
        source_check_id = None
        researcher_profile_id = None
        source_check_ids = None
        researcher_profile_ids = data.researcher_profile_ids

    # ─── Single source check (full | executive_summary) ───────────────
    elif data.source_check_id:
        result = await db.execute(
            select(SourceCheck).where(SourceCheck.id == data.source_check_id)
        )
        check = result.scalar_one_or_none()
        if not check:
            raise HTTPException(status_code=404, detail="Source check not found")
        if check.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to use this source check")
        check_data = await _load_check_data(check, db)
        narrative = await generate_source_check_narrative(check_data)
        if template == "executive_summary":
            html = render_executive_summary_report(check_data, narrative, branding=branding)
            title = f"Executive Summary: {check.input_title or 'Report'}"
        else:
            html = render_source_check_report(check_data, narrative, branding=branding)
            title = f"Source Verification: {check.input_title or 'Report'}"
        report_type = "source_verification"
        source_check_id = check.id
        researcher_profile_id = None
        source_check_ids = None
        researcher_profile_ids = None

    # ─── Single researcher (full | executive_summary) ─────────────────
    else:
        result = await db.execute(
            select(ResearcherProfile).where(
                ResearcherProfile.id == data.researcher_profile_id
            )
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Researcher profile not found")
        if profile.user_id != user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to use this researcher profile"
            )
        profile_data = await _load_researcher_data(profile, db)
        narrative = await generate_researcher_narrative(profile_data)
        if template == "executive_summary":
            html = render_executive_summary_report(profile_data, narrative, branding=branding)
            title = f"Executive Summary: {profile.researcher_name}"
        else:
            html = render_researcher_report(profile_data, narrative, branding=branding)
            title = f"Researcher Integrity: {profile.researcher_name}"
        report_type = "researcher_integrity"
        source_check_id = None
        researcher_profile_id = profile.id
        source_check_ids = None
        researcher_profile_ids = None

    # ─── Render PDF + persist ─────────────────────────────────────────
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
        source_check_ids=source_check_ids,
        researcher_profile_ids=researcher_profile_ids,
        report_type=report_type,
        template=template,
        title=title,
        summary=(narrative or "")[:2000],
        pdf_path=pdf_path,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return _report_response(report)


# ─── List / fetch ─────────────────────────────────────────────────────────


@router.get("/", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user's reports."""
    user_id = current_user.id
    total_q = await db.execute(
        select(func.count(Report.id)).where(
            Report.user_id == user_id, Report.deleted_at.is_(None)
        )
    )
    total = total_q.scalar() or 0

    result = await db.execute(
        select(Report)
        .where(Report.user_id == user_id, Report.deleted_at.is_(None))
        .order_by(Report.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return ReportListResponse(
        items=[_report_response(r) for r in result.scalars().all()],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/shared/{share_token}", response_model=ReportResponse)
async def get_shared_report(share_token: str, db: AsyncSession = Depends(get_db)):
    """Public report access (no auth required) — keyed by share token."""
    result = await db.execute(
        select(Report).where(
            Report.share_token == share_token, Report.deleted_at.is_(None)
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_response(report)


@router.get("/shared/{share_token}/download")
async def download_shared_report(share_token: str, db: AsyncSession = Depends(get_db)):
    """Public PDF download — requires the unguessable share token, not auth."""
    result = await db.execute(
        select(Report).where(
            Report.share_token == share_token, Report.deleted_at.is_(None)
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return await _serve_report_pdf(report, db)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get report details. Owner-only — public sharing goes through `/shared/{token}`."""
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.deleted_at.is_(None))
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this report")
    return _report_response(report)


# ─── Annotations ──────────────────────────────────────────────────────────


@router.put("/{report_id}/annotations", response_model=ReportResponse)
async def update_report_annotations(
    report_id: str,
    data: ReportAnnotationsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Replace the report's annotations list. Annotations re-render at the
    top of the PDF; we drop the cached pdf_path so the next download
    regenerates with the new notes."""
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.deleted_at.is_(None))
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to annotate this report")

    now_iso = datetime.now(timezone.utc).isoformat()
    author = current_user.full_name or current_user.email or "Author"
    report.annotations = [
        {"text": a.text, "author_name": author, "created_at": now_iso}
        for a in data.annotations
    ]

    # Invalidate cached PDF — regenerate on next download.
    if report.pdf_path:
        try:
            if os.path.exists(report.pdf_path):
                os.remove(report.pdf_path)
        except OSError:
            logger.debug("Could not remove cached PDF for report %s", report.id)
        report.pdf_path = None

    await db.commit()
    await db.refresh(report)
    return _report_response(report)


# ─── PDF download ─────────────────────────────────────────────────────────


async def _regenerate_report_pdf(report: Report, db: AsyncSession) -> bytes:
    """Rebuild the PDF from the report's related data when the cached file
    is missing. Uses the stored summary as the narrative — no Gemini call."""
    narrative = report.summary or ""
    template = report.template or "full"

    # Resolve owner's branding for white-label re-render.
    owner_q = await db.execute(select(User).where(User.id == report.user_id))
    owner = owner_q.scalar_one_or_none()
    branding = await _branding_for_user(owner, db) if owner else None

    if template == "comparison":
        ids = list(report.source_check_ids or [])
        if not ids:
            raise HTTPException(status_code=410, detail="Comparison report has no source checks recorded")
        result = await db.execute(select(SourceCheck).where(SourceCheck.id.in_(ids)))
        checks = list(result.scalars().all())
        if not checks:
            raise HTTPException(status_code=410, detail="Underlying source checks no longer exist")
        items = [await _load_check_data(c, db) for c in checks]
        html = render_comparison_report(items, branding=branding, annotations=report.annotations)

    elif template == "institutional_audit":
        ids = list(report.researcher_profile_ids or [])
        if not ids:
            raise HTTPException(status_code=410, detail="Audit report has no researcher profiles recorded")
        result = await db.execute(select(ResearcherProfile).where(ResearcherProfile.id.in_(ids)))
        profiles = list(result.scalars().all())
        if not profiles:
            raise HTTPException(status_code=410, detail="Underlying researcher profiles no longer exist")
        items = [await _load_researcher_data(p, db) for p in profiles]
        html = render_institutional_audit_report(items, branding=branding, annotations=report.annotations)

    elif report.source_check_id:
        sc_result = await db.execute(
            select(SourceCheck).where(SourceCheck.id == report.source_check_id)
        )
        check = sc_result.scalar_one_or_none()
        if not check:
            raise HTTPException(status_code=410, detail="Underlying source check no longer exists")
        check_data = await _load_check_data(check, db)
        if template == "executive_summary":
            html = render_executive_summary_report(
                check_data, narrative, branding=branding, annotations=report.annotations
            )
        else:
            html = render_source_check_report(
                check_data, narrative, branding=branding, annotations=report.annotations
            )

    elif report.researcher_profile_id:
        rp_result = await db.execute(
            select(ResearcherProfile).where(
                ResearcherProfile.id == report.researcher_profile_id
            )
        )
        profile = rp_result.scalar_one_or_none()
        if not profile:
            raise HTTPException(
                status_code=410, detail="Underlying researcher profile no longer exists"
            )
        profile_data = await _load_researcher_data(profile, db)
        if template == "executive_summary":
            html = render_executive_summary_report(
                profile_data, narrative, branding=branding, annotations=report.annotations
            )
        else:
            html = render_researcher_report(
                profile_data, narrative, branding=branding, annotations=report.annotations
            )

    else:
        raise HTTPException(
            status_code=500,
            detail="Report has no underlying source or researcher record",
        )

    return html_to_pdf(html)


@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download PDF report. Regenerates on the fly if the cached file is missing —
    Local generated reports may not yet have a cached artifact.

    Owner-only. Public sharing of the *PDF* goes through ``/shared/{token}/download``.
    """
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.deleted_at.is_(None))
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to download this report")
    return await _serve_report_pdf(report, db)


async def _serve_report_pdf(report: Report, db: AsyncSession) -> Response:
    """Render or load the PDF for a Report and return it as an HTTP attachment."""
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
