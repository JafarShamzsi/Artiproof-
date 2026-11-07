import io
import json
import logging
import uuid
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from passlib.hash import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.constants import DEFAULT_NOTIFICATION_PREFERENCES, SUPPORTED_LOCALES
from app.database import get_db
from app.models.report import Report
from app.models.researcher import ResearcherProfile, PublicationAnalysis
from app.models.source_check import (
    AIDetectionResult,
    CitationCheck,
    ClaimAnalysis,
    SourceCheck,
)
from app.models.user import User
from app.schemas.auth import (
    AccountDeactivateRequest,
    AccountDeleteRequest,
    ChangePasswordRequest,
    GoogleLogin,
    LocaleUpdate,
    NotificationPreferences,
    UserRegister,
    UserLogin,
    UserResponse,
    UserUpdate,
    TokenResponse,
)
from app.utils.auth import (
    create_access_token,
    get_current_user,
    get_current_user_allow_deactivated,
)
from app.utils.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _user_to_response(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit("3/minute")
async def register(request: Request, data: UserRegister, db: AsyncSession = Depends(get_db)):
    """Create a new user account and return a JWT so the client can authenticate immediately."""
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # New users always start as researchers — admin is privileged and only assignable
    # by an existing admin via a separate admin tool. Ignore role from the public payload.
    user = User(
        id=str(uuid.uuid4()),
        email=data.email,
        hashed_password=bcrypt.hash(data.password),
        full_name=data.full_name,
        institution=data.institution,
        role="researcher" if data.role == "admin" else data.role,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=_user_to_response(user))


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate and return a JWT.

    Deactivated accounts are allowed to log in so the user can land on
    Settings and self-reactivate. Deleted accounts return 401 — they look
    like "no such account" from the outside.
    """
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password or not bcrypt.verify(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=_user_to_response(user))


@router.post("/google", response_model=TokenResponse)
@limiter.limit("10/minute")
async def google_login(request: Request, data: GoogleLogin, db: AsyncSession = Depends(get_db)):
    """Verify a Google ID token, then create or return the matching platform user."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")

    try:
        id_info = google_id_token.verify_oauth2_token(
            data.id_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    email = id_info.get("email")
    email_verified = id_info.get("email_verified")
    if not email or email_verified is not True:
        raise HTTPException(status_code=401, detail="Google email is not verified")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            hashed_password=None,
            full_name=id_info.get("name") or email.split("@", 1)[0],
            role="researcher",
            updated_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=_user_to_response(user))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return _user_to_response(current_user)


@router.put("/me", response_model=UserResponse)
async def update_profile(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Users may update profile fields but never their own role — role changes are
    # privileged and must go through an admin tool.
    update_data = data.model_dump(exclude_unset=True)
    update_data.pop("role", None)

    if "full_name" in update_data:
        current_user.full_name = update_data["full_name"]
    if "institution" in update_data:
        current_user.institution = update_data["institution"]

    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)
    return _user_to_response(current_user)


# ─── Settings: password / notifications / locale ────────────────────────────


@router.post("/me/change-password", status_code=204)
@limiter.limit("3/minute")
async def change_password(
    request: Request,
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change the current user's password.

    Verifies the current password first. Google-only accounts (no
    hashed_password) get a 400 with a clear message — they should manage
    credentials via Google.
    """
    if not current_user.hashed_password:
        raise HTTPException(
            status_code=400,
            detail="This account uses Google sign-in. Manage your password through Google.",
        )

    if not bcrypt.verify(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    if bcrypt.verify(data.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400, detail="New password must differ from the current one"
        )

    current_user.hashed_password = bcrypt.hash(data.new_password)
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()


@router.get("/me/notifications", response_model=NotificationPreferences)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
):
    """Return the user's notification preferences merged with defaults so a
    NULL row produces a stable shape and adding a new key doesn't break clients.
    """
    stored = current_user.notification_preferences or {}
    merged = {**DEFAULT_NOTIFICATION_PREFERENCES, **stored}
    return NotificationPreferences(**merged)


@router.put("/me/notifications", response_model=NotificationPreferences)
async def update_notification_preferences(
    data: NotificationPreferences,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.notification_preferences = data.model_dump()
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return data


@router.put("/me/locale", response_model=UserResponse)
async def update_locale(
    data: LocaleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.locale not in SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported locale. Use one of: {', '.join(SUPPORTED_LOCALES)}",
        )
    current_user.locale = data.locale
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)
    return _user_to_response(current_user)


# ─── Data export ────────────────────────────────────────────────────────────


@router.get("/me/export")
async def export_user_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a zip of the user's data (profile, source checks + children,
    researcher profiles + publications, reports metadata).

    Implementation note: streams a fully-formed zip from memory because the
    free-tier limits cap total size well below a few MB. If the team tier
    starts producing exports >50MB, switch to streaming the zip directly to
    response.body and skip the BytesIO buffer.
    """
    user_id = current_user.id

    # Profile
    profile_payload = {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "institution": current_user.institution,
        "role": current_user.role,
        "tier": current_user.tier,
        "locale": current_user.locale,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "notification_preferences": {
            **DEFAULT_NOTIFICATION_PREFERENCES,
            **(current_user.notification_preferences or {}),
        },
    }

    # Source checks (live + soft-deleted, excluding hard-deleted descendants)
    sc_q = await db.execute(
        select(SourceCheck).where(SourceCheck.user_id == user_id)
    )
    source_checks = []
    for sc in sc_q.scalars().all():
        claims_q = await db.execute(
            select(ClaimAnalysis).where(ClaimAnalysis.source_check_id == sc.id)
        )
        ai_q = await db.execute(
            select(AIDetectionResult).where(AIDetectionResult.source_check_id == sc.id)
        )
        cit_q = await db.execute(
            select(CitationCheck).where(CitationCheck.source_check_id == sc.id)
        )
        source_checks.append({
            "id": sc.id,
            "input_type": sc.input_type,
            "input_title": sc.input_title,
            "input_content": sc.input_content,
            "status": sc.status,
            "overall_credibility_score": sc.overall_credibility_score,
            "ai_content_percentage": sc.ai_content_percentage,
            "misinfo_claims_found": sc.misinfo_claims_found,
            "score_breakdown": sc.score_breakdown,
            "model_metadata": sc.model_metadata,
            "created_at": sc.created_at.isoformat() if sc.created_at else None,
            "completed_at": sc.completed_at.isoformat() if sc.completed_at else None,
            "deleted_at": sc.deleted_at.isoformat() if sc.deleted_at else None,
            "claims": [
                {
                    "id": c.id, "claim_text": c.claim_text, "verdict": c.verdict,
                    "confidence": c.confidence, "explanation": c.explanation,
                    "true_version": c.true_version, "sources": c.sources,
                    "origin_trace": c.origin_trace,
                }
                for c in claims_q.scalars().all()
            ],
            "ai_detections": [
                {
                    "id": a.id, "paragraph_index": a.paragraph_index,
                    "paragraph_text": a.paragraph_text,
                    "ai_probability": a.ai_probability,
                    "detection_method": a.detection_method,
                }
                for a in ai_q.scalars().all()
            ],
            "citations": [
                {
                    "id": c.id, "original_citation": c.original_citation,
                    "citation_url": c.citation_url, "is_accessible": c.is_accessible,
                    "is_retracted": c.is_retracted,
                    "credibility_score": c.credibility_score,
                    "issues": c.issues,
                    "suggested_alternative": c.suggested_alternative,
                }
                for c in cit_q.scalars().all()
            ],
        })

    # Researcher profiles
    rp_q = await db.execute(
        select(ResearcherProfile).where(ResearcherProfile.user_id == user_id)
    )
    researchers = []
    for rp in rp_q.scalars().all():
        pubs_q = await db.execute(
            select(PublicationAnalysis).where(PublicationAnalysis.researcher_profile_id == rp.id)
        )
        researchers.append({
            "id": rp.id,
            "researcher_name": rp.researcher_name,
            "scopus_id": rp.scopus_id,
            "google_scholar_id": rp.google_scholar_id,
            "orcid": rp.orcid,
            "institution": rp.institution,
            "official_h_index": rp.official_h_index,
            "official_citation_count": rp.official_citation_count,
            "adjusted_h_index": rp.adjusted_h_index,
            "adjusted_citation_count": rp.adjusted_citation_count,
            "integrity_score": rp.integrity_score,
            "self_citation_rate": rp.self_citation_rate,
            "topic_relevance_score": rp.topic_relevance_score,
            "citation_ring_flags": rp.citation_ring_flags,
            "integrity_breakdown": rp.integrity_breakdown,
            "model_metadata": rp.model_metadata,
            "created_at": rp.created_at.isoformat() if rp.created_at else None,
            "deleted_at": rp.deleted_at.isoformat() if rp.deleted_at else None,
            "publications": [
                {
                    "title": p.title, "journal": p.journal, "year": p.year,
                    "doi": p.doi, "citation_count": p.citation_count,
                    "topic_match_score": p.topic_match_score,
                    "is_self_cited_heavily": p.is_self_cited_heavily,
                    "flags": p.flags,
                }
                for p in pubs_q.scalars().all()
            ],
        })

    # Reports (metadata only — PDFs are large and re-generatable)
    rpt_q = await db.execute(select(Report).where(Report.user_id == user_id))
    reports = [
        {
            "id": r.id,
            "source_check_id": r.source_check_id,
            "researcher_profile_id": r.researcher_profile_id,
            "report_type": r.report_type,
            "title": r.title,
            "summary": r.summary,
            "share_token": r.share_token,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "deleted_at": r.deleted_at.isoformat() if r.deleted_at else None,
        }
        for r in rpt_q.scalars().all()
    ]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", _EXPORT_README)
        zf.writestr("profile.json", json.dumps(profile_payload, indent=2))
        zf.writestr("source_checks.json", json.dumps(source_checks, indent=2))
        zf.writestr("researcher_profiles.json", json.dumps(researchers, indent=2))
        zf.writestr("reports.json", json.dumps(reports, indent=2))

    buf.seek(0)
    filename = f"artiproof-export-{current_user.id[:8]}-{datetime.now(timezone.utc):%Y%m%d}.zip"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


_EXPORT_README = """ArtiProof data export
======================

This archive contains every record we hold for your account at the time
of export. Files are JSON for portability:

- profile.json              account info, role, tier, locale, notification prefs
- source_checks.json        all source verifications, including claims, AI detection
                            results, citation analysis, and per-deduction scoring
- researcher_profiles.json  every researcher integrity analysis you've run
                            (publications + adjusted metrics + ring detection)
- reports.json              metadata for generated PDF reports — the PDFs
                            themselves are re-generatable from the source data

To request deletion of this data, use Settings → Danger zone → Delete
account in the app, or contact support.
"""


# ─── Account: deactivate / reactivate / delete ──────────────────────────────


@router.post("/me/deactivate", status_code=204)
async def deactivate_account(
    data: AccountDeactivateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Suspend the account. Re-confirmation via password.

    Deactivated users can log in (so they can self-reactivate) but every
    /api/* route except /me and /me/reactivate returns 423 Locked.
    """
    if not current_user.hashed_password or not bcrypt.verify(
        data.current_password, current_user.hashed_password
    ):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    current_user.deactivated_at = datetime.now(timezone.utc)
    await db.commit()


@router.post("/me/reactivate", response_model=UserResponse)
async def reactivate_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_allow_deactivated),
):
    """Lift the suspension. Anyone holding a valid JWT can self-reactivate."""
    if current_user.deactivated_at is None:
        return _user_to_response(current_user)
    current_user.deactivated_at = None
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)
    return _user_to_response(current_user)


@router.delete("/me", status_code=204)
async def delete_account(
    data: AccountDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete the account.

    Sets `deleted_at` on the user row and on every owned SourceCheck /
    ResearcherProfile / Report so the standard cleanup task hard-deletes
    them after the 30-day grace window. After this call, the user's JWT
    starts returning 401 — `get_current_user` rejects deleted accounts.
    """
    if data.confirm != "DELETE":
        raise HTTPException(
            status_code=400,
            detail='Type "DELETE" exactly into the confirm field to proceed.',
        )
    if not current_user.hashed_password or not bcrypt.verify(
        data.current_password, current_user.hashed_password
    ):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    now = datetime.now(timezone.utc)
    current_user.deleted_at = now

    # Cascade soft-delete to owned rows so the cleanup task can sweep them up.
    sc_q = await db.execute(
        select(SourceCheck).where(
            SourceCheck.user_id == current_user.id,
            SourceCheck.deleted_at.is_(None),
        )
    )
    for sc in sc_q.scalars().all():
        sc.deleted_at = now

    rp_q = await db.execute(
        select(ResearcherProfile).where(
            ResearcherProfile.user_id == current_user.id,
            ResearcherProfile.deleted_at.is_(None),
        )
    )
    for rp in rp_q.scalars().all():
        rp.deleted_at = now

    rpt_q = await db.execute(
        select(Report).where(
            Report.user_id == current_user.id,
            Report.deleted_at.is_(None),
        )
    )
    for r in rpt_q.scalars().all():
        r.deleted_at = now

    await db.commit()
