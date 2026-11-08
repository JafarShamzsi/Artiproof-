import asyncio
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.organization import Organization
from app.models.report import Report, _default_share_expires_at
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
from app.utils.ownership import is_owner_or_org_admin
from app.utils.quota import enforce_quota
from app.utils.rate_limit import limiter, tier_aware_limit_for_key

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
    renderer expects. Centralized so /generate and /regenerate share it.

    For multi-check templates (comparison, institutional audit) prefer
    ``_load_check_summaries_batched`` — calling this one in a loop is
    ``2N`` queries.
    """
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


async def _load_check_summaries_batched(
    checks: list[SourceCheck], db: AsyncSession
) -> list[dict]:
    """Comparison-template loader: returns one summary dict per check
    using a *single* citation query across all ids (not 2 queries per
    item like ``_load_check_data``). The comparison renderer only reads
    the citation count + retracted flag, so we skip claims entirely.
    """
    if not checks:
        return []
    ids = [c.id for c in checks]
    citations_by_check: dict[str, list[CitationCheck]] = {cid: [] for cid in ids}
    cit_q = await db.execute(
        select(CitationCheck).where(CitationCheck.source_check_id.in_(ids))
    )
    for cit in cit_q.scalars().all():
        citations_by_check.setdefault(cit.source_check_id, []).append(cit)

    return [
        {
            "input_title": check.input_title,
            "input_type": check.input_type,
            "overall_credibility_score": check.overall_credibility_score or 0,
            "ai_content_percentage": check.ai_content_percentage or 0,
            "misinfo_claims_found": check.misinfo_claims_found or 0,
            "claims": [],
            "citations": [
                {
                    "is_retracted": c.is_retracted,
                    "is_accessible": c.is_accessible,
                }
                for c in citations_by_check.get(check.id, [])
            ],
        }
        for check in checks
    ]


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


def _researcher_summaries(profiles: list[ResearcherProfile]) -> list[dict]:
    """Audit-template loader: the institutional-audit renderer reads only
    profile-level fields, so we skip the per-researcher publication
    query entirely (legacy ``_load_researcher_data`` issued one query
    per profile)."""
    return [
        {
            "researcher_name": p.researcher_name,
            "institution": p.institution,
            "official_h_index": p.official_h_index,
            "adjusted_h_index": p.adjusted_h_index,
            "integrity_score": p.integrity_score,
            "self_citation_rate": p.self_citation_rate,
            "citation_ring_flags": p.citation_ring_flags,
        }
        for p in profiles
    ]


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
        share_expires_at=getattr(r, "share_expires_at", None),
        annotations=getattr(r, "annotations", None),
        source_check_ids=getattr(r, "source_check_ids", None),
        researcher_profile_ids=getattr(r, "researcher_profile_ids", None),
        created_at=r.created_at,
    )


# ─── Generate ─────────────────────────────────────────────────────────────


@router.post("/generate", response_model=ReportResponse, status_code=201)
@limiter.limit(tier_aware_limit_for_key)
async def generate_report(
    request: Request,
    data: ReportGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(enforce_quota("reports")),
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
        # De-duplicate first so a payload like [a, a, a] doesn't satisfy
        # the "all ids exist" check while collapsing to a single source.
        # Preserve order via dict.fromkeys for downstream stability.
        sc_ids = list(dict.fromkeys(data.source_check_ids))
        if len(sc_ids) < 2:
            raise HTTPException(
                status_code=400,
                detail="Comparison requires at least 2 distinct source check ids",
            )
        # Exclude soft-deleted rows — a fresh share-link generation must
        # never resurrect content the user removed (mirrors the policy
        # used by _regenerate_report_pdf).
        result = await db.execute(
            select(SourceCheck).where(
                SourceCheck.id.in_(sc_ids),
                SourceCheck.deleted_at.is_(None),
            )
        )
        checks = list(result.scalars().all())
        if len(checks) != len(sc_ids):
            raise HTTPException(status_code=404, detail="One or more source checks not found")
        for c in checks:
            if not is_owner_or_org_admin(current_user, c):
                raise HTTPException(status_code=403, detail="Not authorized to use one of the source checks")
        items = await _load_check_summaries_batched(checks, db)
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
        # Same de-dup + soft-delete filter as the comparison branch above.
        rp_ids = list(dict.fromkeys(data.researcher_profile_ids))
        if len(rp_ids) < 2:
            raise HTTPException(
                status_code=400,
                detail="Audit requires at least 2 distinct researcher profile ids",
            )
        result = await db.execute(
            select(ResearcherProfile).where(
                ResearcherProfile.id.in_(rp_ids),
                ResearcherProfile.deleted_at.is_(None),
            )
        )
        profiles = list(result.scalars().all())
        if len(profiles) != len(rp_ids):
            raise HTTPException(status_code=404, detail="One or more researcher profiles not found")
        for p in profiles:
            if not is_owner_or_org_admin(current_user, p):
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to use one of the researcher profiles",
                )
        items = _researcher_summaries(profiles)
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
        # Soft-deleted check is treated as missing — a fresh report
        # generation must never resurrect data the user removed.
        result = await db.execute(
            select(SourceCheck).where(
                SourceCheck.id == data.source_check_id,
                SourceCheck.deleted_at.is_(None),
            )
        )
        check = result.scalar_one_or_none()
        if not check:
            raise HTTPException(status_code=404, detail="Source check not found")
        if not is_owner_or_org_admin(current_user, check):
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
        # Same soft-delete filter as the source-check branch.
        result = await db.execute(
            select(ResearcherProfile).where(
                ResearcherProfile.id == data.researcher_profile_id,
                ResearcherProfile.deleted_at.is_(None),
            )
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Researcher profile not found")
        if not is_owner_or_org_admin(current_user, profile):
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
    # WeasyPrint + filesystem writes are synchronous and CPU-bound — run
    # them in a worker thread so the event loop doesn't stall on a slow
    # render. html_to_pdf now returns (bytes, renderer_label) so the
    # download route can stamp X-Report-Renderer for the frontend.
    try:
        pdf_bytes, _renderer = await asyncio.to_thread(html_to_pdf, html)
        pdf_path = await asyncio.to_thread(save_pdf, pdf_bytes)
    except Exception:
        logger.exception("PDF generation failed")
        pdf_path = None

    report = Report(
        user_id=user_id,
        organization_id=current_user.organization_id,
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


def _share_link_alive(report: Report) -> bool:
    """A share link is alive if the report isn't soft-deleted and the
    expiry hasn't passed. NULL expiry exists only for legacy pre-0010
    rows in test fixtures and is treated as alive (the migration
    backfills real DB rows)."""
    if report.deleted_at is not None:
        return False
    expires = getattr(report, "share_expires_at", None)
    if expires is None:
        return True
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires > datetime.now(timezone.utc)


@router.get("/shared/{share_token}", response_model=ReportResponse)
async def get_shared_report(share_token: str, db: AsyncSession = Depends(get_db)):
    """Public report access (no auth required) — keyed by share token.

    The token is unguessable (32-byte urlsafe), but the link expires on
    ``share_expires_at`` (default 90d) so a leaked URL doesn't grant
    forever-access. Owner can rotate via ``/{id}/rotate-share-token``.
    """
    result = await db.execute(
        select(Report).where(
            Report.share_token == share_token, Report.deleted_at.is_(None)
        )
    )
    report = result.scalar_one_or_none()
    if not report or not _share_link_alive(report):
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_response(report)


@router.get("/shared/{share_token}/download")
async def download_shared_report(share_token: str, db: AsyncSession = Depends(get_db)):
    """Public PDF download — requires the unguessable share token, not auth.
    Rejects expired links the same way as the JSON endpoint."""
    result = await db.execute(
        select(Report).where(
            Report.share_token == share_token, Report.deleted_at.is_(None)
        )
    )
    report = result.scalar_one_or_none()
    if not report or not _share_link_alive(report):
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
    if not is_owner_or_org_admin(current_user, report):
        raise HTTPException(status_code=403, detail="Not authorized to view this report")
    return _report_response(report)


@router.post("/{report_id}/rotate-share-token", response_model=ReportResponse)
async def rotate_share_token(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Issue a fresh share token + reset the expiry. Invalidates any
    existing share link (the old token won't match anymore). Use this
    after suspecting a leak or before re-sharing publicly."""
    result = await db.execute(
        select(Report).where(Report.id == report_id, Report.deleted_at.is_(None))
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not is_owner_or_org_admin(current_user, report):
        raise HTTPException(status_code=403, detail="Not authorized to rotate this token")
    report.share_token = secrets.token_urlsafe(32)
    report.share_expires_at = _default_share_expires_at()
    await db.commit()
    await db.refresh(report)
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
    if not is_owner_or_org_admin(current_user, report):
        raise HTTPException(status_code=403, detail="Not authorized to annotate this report")

    now_iso = datetime.now(timezone.utc).isoformat()
    author = current_user.full_name or current_user.email or "Author"
    report.annotations = [
        {"text": a.text, "author_name": author, "created_at": now_iso}
        for a in data.annotations
    ]

    # Cache invalidation order matters here: commit pdf_path=None FIRST,
    # then unlink the file. The reverse order races: a concurrent
    # download between os.remove() and commit() reads the stale path
    # from the DB, finds no file, falls back to regen — but regen reads
    # the still-uncommitted old annotations and serves a stale PDF
    # despite this PUT having "succeeded".
    cached_path = report.pdf_path
    if cached_path:
        report.pdf_path = None
    await db.commit()
    await db.refresh(report)

    if cached_path:
        try:
            if await asyncio.to_thread(os.path.exists, cached_path):
                await asyncio.to_thread(os.remove, cached_path)
        except OSError:
            logger.debug("Could not remove cached PDF for report %s", report.id)

    return _report_response(report)


# ─── PDF download ─────────────────────────────────────────────────────────


async def _regenerate_report_pdf(report: Report, db: AsyncSession) -> tuple[bytes, str]:
    """Rebuild the PDF from the report's related data when the cached file
    is missing. Uses the stored summary as the narrative — no Gemini call.

    Returns (pdf_bytes, renderer_label) — the route uses ``renderer_label``
    to stamp ``X-Report-Renderer`` so the frontend can surface a caveat
    toast when the PyMuPDF fallback was used."""
    narrative = report.summary or ""
    template = report.template or "full"

    # Resolve owner's branding for white-label re-render.
    owner_q = await db.execute(select(User).where(User.id == report.user_id))
    owner = owner_q.scalar_one_or_none()
    branding = await _branding_for_user(owner, db) if owner else None

    # Soft-deleted upstream records (deleted_at IS NOT NULL) must NOT be
    # rendered into a re-generated PDF — the share link would otherwise
    # leak data the owner asked to be removed. Every branch filters
    # ``deleted_at.is_(None)``.
    if template == "comparison":
        ids = list(report.source_check_ids or [])
        if not ids:
            raise HTTPException(status_code=410, detail="Comparison report has no source checks recorded")
        result = await db.execute(
            select(SourceCheck).where(
                SourceCheck.id.in_(ids), SourceCheck.deleted_at.is_(None)
            )
        )
        checks = list(result.scalars().all())
        if not checks:
            raise HTTPException(status_code=410, detail="Underlying source checks no longer exist")
        items = await _load_check_summaries_batched(checks, db)
        html = render_comparison_report(items, branding=branding, annotations=report.annotations)

    elif template == "institutional_audit":
        ids = list(report.researcher_profile_ids or [])
        if not ids:
            raise HTTPException(status_code=410, detail="Audit report has no researcher profiles recorded")
        result = await db.execute(
            select(ResearcherProfile).where(
                ResearcherProfile.id.in_(ids),
                ResearcherProfile.deleted_at.is_(None),
            )
        )
        profiles = list(result.scalars().all())
        if not profiles:
            raise HTTPException(status_code=410, detail="Underlying researcher profiles no longer exist")
        items = _researcher_summaries(profiles)
        html = render_institutional_audit_report(items, branding=branding, annotations=report.annotations)

    elif report.source_check_id:
        sc_result = await db.execute(
            select(SourceCheck).where(
                SourceCheck.id == report.source_check_id,
                SourceCheck.deleted_at.is_(None),
            )
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
                ResearcherProfile.id == report.researcher_profile_id,
                ResearcherProfile.deleted_at.is_(None),
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

    # html_to_pdf returns (bytes, renderer_label) — pass both upstream
    # so the route can stamp the X-Report-Renderer response header.
    return await asyncio.to_thread(html_to_pdf, html)  # type: ignore[return-value]


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
    if not is_owner_or_org_admin(current_user, report):
        raise HTTPException(status_code=403, detail="Not authorized to download this report")
    return await _serve_report_pdf(report, db)


async def _serve_report_pdf(report: Report, db: AsyncSession) -> Response:
    """Render or load the PDF for a Report and return it as an HTTP attachment.

    Sets ``X-Report-Renderer`` to indicate whether the bytes came from
    the styled WeasyPrint path or the plain-text PyMuPDF fallback. The
    frontend uses this to toast "styled rendering unavailable" so the
    user understands why the PDF looks bare.
    """

    def _read_cached(path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    renderer = "cached"
    if report.pdf_path and await asyncio.to_thread(os.path.exists, report.pdf_path):
        pdf_bytes = await asyncio.to_thread(_read_cached, report.pdf_path)
    else:
        try:
            pdf_bytes, renderer = await _regenerate_report_pdf(report, db)
        except HTTPException:
            raise
        except Exception:
            logger.exception("PDF regeneration failed for report %s", report.id)
            raise HTTPException(status_code=500, detail="PDF generation failed")

        # Best-effort cache the freshly rendered PDF. Filesystem may be read-only
        # or ephemeral; failure here is fine — we already have the bytes.
        try:
            new_path = await asyncio.to_thread(save_pdf, pdf_bytes)
            report.pdf_path = new_path
            await db.commit()
        except Exception:
            logger.debug("Could not persist regenerated PDF path (ephemeral fs?)")

    filename = f"artiproof-report-{report.id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Report-Renderer": renderer,
        },
    )
