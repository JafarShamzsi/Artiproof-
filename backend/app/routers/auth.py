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
from app.constants import (
    DEFAULT_ANALYSIS_PREFERENCES,
    DEFAULT_NOTIFICATION_PREFERENCES,
    SUPPORTED_LOCALES,
)
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
    AnalysisPreferences,
    ChangePasswordRequest,
    ConnectionItem,
    GoogleLogin,
    GoogleLinkRequest,
    LocaleUpdate,
    LoginChallengeResponse,
    LoginTwoFactorRequest,
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
from app.routers.security import _verify_totp_or_backup, issue_login_token

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

    token, _ = await issue_login_token(db, user, request)
    return TokenResponse(access_token=token, user=_user_to_response(user))


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate and return a JWT, OR a 2FA challenge token.

    When the account has TOTP enabled the response is a LoginChallengeResponse
    (challenge_token: short-lived, single-use) and the frontend must POST it
    back to /api/auth/login/2fa with a code to receive the access token.

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

    if user.totp_enabled:
        # Issue a 2FA challenge token. We're reusing AuthToken with a fresh
        # `kind` so we don't need a separate table; TTL is short (10 min) and
        # single-use just like password-reset tokens.
        from app.models.auth_token import AuthToken
        from datetime import timedelta as _td

        challenge = AuthToken(
            user_id=user.id,
            kind="2fa_challenge",
            expires_at=datetime.now(timezone.utc) + _td(minutes=10),
        )
        db.add(challenge)
        await db.commit()
        await db.refresh(challenge)
        return LoginChallengeResponse(challenge_token=challenge.id)

    token, _ = await issue_login_token(db, user, request)
    return TokenResponse(access_token=token, user=_user_to_response(user))


@router.post("/login/2fa", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login_two_factor(
    request: Request,
    data: LoginTwoFactorRequest,
    db: AsyncSession = Depends(get_db),
):
    """Step 2 of the 2FA login flow. Consumes the challenge token + a 6-digit
    TOTP or 8-char backup code, returns the actual access token."""
    from app.models.auth_token import AuthToken

    challenge = await db.get(AuthToken, data.challenge_token)
    now = datetime.now(timezone.utc)
    if (
        challenge is None
        or challenge.kind != "2fa_challenge"
        or challenge.used_at is not None
        or challenge.expires_at < now
    ):
        raise HTTPException(status_code=401, detail="Invalid or expired challenge")

    user = await db.get(User, challenge.user_id)
    if user is None or user.deleted_at is not None or not user.totp_enabled:
        raise HTTPException(status_code=401, detail="Invalid or expired challenge")

    if not _verify_totp_or_backup(user, data.code):
        raise HTTPException(status_code=401, detail="Invalid 2FA code")

    challenge.used_at = now
    await db.commit()

    token, _ = await issue_login_token(db, user, request)
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

    google_sub = id_info.get("sub")
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

    # Record / refresh the linked provider so the Settings UI can show "linked".
    if google_sub:
        linked = dict(user.linked_providers or {})
        linked["google"] = {
            "sub": google_sub,
            "email": email,
            "linked_at": (linked.get("google") or {}).get("linked_at")
            or datetime.now(timezone.utc).isoformat(),
        }
        user.linked_providers = linked
        await db.commit()

    if user.totp_enabled:
        from app.models.auth_token import AuthToken
        from datetime import timedelta as _td

        challenge = AuthToken(
            user_id=user.id,
            kind="2fa_challenge",
            expires_at=datetime.now(timezone.utc) + _td(minutes=10),
        )
        db.add(challenge)
        await db.commit()
        await db.refresh(challenge)
        return LoginChallengeResponse(challenge_token=challenge.id)

    token, _ = await issue_login_token(db, user, request)
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


# ─── Connected accounts ────────────────────────────────────────────────────


@router.get("/me/connections", response_model=list[ConnectionItem])
async def list_connections(current_user: User = Depends(get_current_user)):
    """Return the status of every supported provider, linked or not.

    Today only Google is supported. Frontend renders a row per provider
    so adding a new one means adding it to this list and to /connections/<p>.
    """
    linked = current_user.linked_providers or {}
    g = linked.get("google") if isinstance(linked, dict) else None
    items = [
        ConnectionItem(
            provider="google",
            linked=bool(g),
            email=(g or {}).get("email"),
            linked_at=(
                datetime.fromisoformat((g or {}).get("linked_at"))
                if g and (g or {}).get("linked_at")
                else None
            ),
        )
    ]
    return items


@router.post("/me/connections/google", response_model=ConnectionItem)
async def link_google_account(
    data: GoogleLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Link the current user to a Google identity. Verifies the ID token
    against GOOGLE_CLIENT_ID. Refuses if the Google account is already
    linked to a different ArtiProof user."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    try:
        id_info = google_id_token.verify_oauth2_token(
            data.id_token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    google_sub = id_info.get("sub")
    google_email = id_info.get("email")
    if not google_sub:
        raise HTTPException(status_code=400, detail="Google token missing 'sub' claim")

    # Check no other user already has this google sub linked.
    other_q = await db.execute(
        select(User).where(User.id != current_user.id)
    )
    for u in other_q.scalars().all():
        existing = (u.linked_providers or {}).get("google") if u.linked_providers else None
        if existing and existing.get("sub") == google_sub:
            raise HTTPException(
                status_code=409,
                detail="That Google account is already linked to a different ArtiProof user.",
            )

    linked = dict(current_user.linked_providers or {})
    linked["google"] = {
        "sub": google_sub,
        "email": google_email,
        "linked_at": datetime.now(timezone.utc).isoformat(),
    }
    current_user.linked_providers = linked
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return ConnectionItem(
        provider="google",
        linked=True,
        email=google_email,
        linked_at=datetime.now(timezone.utc),
    )


@router.delete("/me/connections/{provider}", status_code=204)
async def unlink_connection(
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unlink a provider. Refuses when it would lock the user out — i.e.
    when there's no password and no other linked provider remaining."""
    if provider != "google":
        raise HTTPException(status_code=404, detail="Unknown provider")

    linked = dict(current_user.linked_providers or {})
    if "google" not in linked:
        raise HTTPException(status_code=404, detail="Google is not linked")

    other_providers = [k for k in linked.keys() if k != provider]
    has_password = bool(current_user.hashed_password)
    if not has_password and not other_providers:
        raise HTTPException(
            status_code=400,
            detail=(
                "Set a password before unlinking — otherwise you'll lose "
                "the ability to sign in."
            ),
        )

    linked.pop("google", None)
    current_user.linked_providers = linked or None
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()


# ─── Default analysis preferences ──────────────────────────────────────────


@router.get("/me/analysis-preferences", response_model=AnalysisPreferences)
async def get_analysis_preferences(current_user: User = Depends(get_current_user)):
    stored = current_user.analysis_preferences or {}
    merged = {**DEFAULT_ANALYSIS_PREFERENCES, **stored}
    return AnalysisPreferences(**merged)


@router.put("/me/analysis-preferences", response_model=AnalysisPreferences)
async def update_analysis_preferences(
    data: AnalysisPreferences,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.analysis_preferences = data.model_dump()
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return data


# ─── Pinned items ─────────────────────────────────────────────────────────


from app.constants import MAX_PINNED_ITEMS  # noqa: E402
from app.schemas.auth import PinnedItem, PinRequest, ShareActivityRequest  # noqa: E402


async def _hydrate_pins(db: AsyncSession, user: User) -> list[PinnedItem]:
    """Hydrate the pinned_items JSON into rich items.

    Pins for rows that no longer exist (deleted, etc.) are silently
    filtered. The JSON column itself isn't pruned here — a separate cleanup
    pass could do that, but tolerating stale entries keeps reads idempotent.
    """
    pins = user.pinned_items or []
    if not isinstance(pins, list):
        return []

    by_kind: dict[str, list[str]] = {"source_check": [], "researcher": [], "report": []}
    pinned_at: dict[tuple[str, str], str | None] = {}
    for p in pins:
        if not isinstance(p, dict):
            continue
        kind = p.get("kind")
        pid = p.get("id")
        if kind not in by_kind or not isinstance(pid, str):
            continue
        by_kind[kind].append(pid)
        pinned_at[(kind, pid)] = p.get("pinned_at")

    out: list[PinnedItem] = []

    if by_kind["source_check"]:
        sc_q = await db.execute(
            select(SourceCheck).where(
                SourceCheck.id.in_(by_kind["source_check"]),
                SourceCheck.user_id == user.id,
                SourceCheck.deleted_at.is_(None),
            )
        )
        for sc in sc_q.scalars().all():
            iso = pinned_at.get(("source_check", sc.id))
            out.append(
                PinnedItem(
                    kind="source_check",
                    id=sc.id,
                    title=sc.input_title or f"Source check ({sc.input_type})",
                    score=sc.overall_credibility_score,
                    pinned_at=datetime.fromisoformat(iso) if iso else sc.created_at,
                )
            )

    if by_kind["researcher"]:
        rp_q = await db.execute(
            select(ResearcherProfile).where(
                ResearcherProfile.id.in_(by_kind["researcher"]),
                ResearcherProfile.user_id == user.id,
                ResearcherProfile.deleted_at.is_(None),
            )
        )
        for rp in rp_q.scalars().all():
            iso = pinned_at.get(("researcher", rp.id))
            out.append(
                PinnedItem(
                    kind="researcher",
                    id=rp.id,
                    title=f"Researcher: {rp.researcher_name}",
                    score=rp.integrity_score,
                    pinned_at=datetime.fromisoformat(iso) if iso else rp.created_at,
                )
            )

    if by_kind["report"]:
        rpt_q = await db.execute(
            select(Report).where(
                Report.id.in_(by_kind["report"]),
                Report.user_id == user.id,
                Report.deleted_at.is_(None),
            )
        )
        for r in rpt_q.scalars().all():
            iso = pinned_at.get(("report", r.id))
            out.append(
                PinnedItem(
                    kind="report",
                    id=r.id,
                    title=r.title,
                    score=None,
                    pinned_at=datetime.fromisoformat(iso) if iso else r.created_at,
                )
            )

    out.sort(key=lambda p: p.pinned_at, reverse=True)
    return out


@router.get("/me/pins", response_model=list[PinnedItem])
async def list_pins(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _hydrate_pins(db, current_user)


@router.post("/me/pins", response_model=list[PinnedItem], status_code=201)
async def add_pin(
    data: PinRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pin an item to the dashboard. Verifies ownership before pinning so
    a user can't pin something they don't own. Idempotent — pinning an
    already-pinned item returns the current list."""
    if data.kind == "source_check":
        target = await db.get(SourceCheck, data.id)
    elif data.kind == "researcher":
        target = await db.get(ResearcherProfile, data.id)
    elif data.kind == "report":
        target = await db.get(Report, data.id)
    else:
        raise HTTPException(status_code=400, detail="Invalid kind")

    if target is None or target.user_id != current_user.id:
        raise HTTPException(status_code=404, detail=f"{data.kind} not found")
    if getattr(target, "deleted_at", None) is not None:
        raise HTTPException(status_code=404, detail=f"{data.kind} not found")

    pins = list(current_user.pinned_items or [])
    if any(
        isinstance(p, dict) and p.get("kind") == data.kind and p.get("id") == data.id
        for p in pins
    ):
        return await _hydrate_pins(db, current_user)
    if len(pins) >= MAX_PINNED_ITEMS:
        raise HTTPException(
            status_code=400,
            detail=f"You can pin at most {MAX_PINNED_ITEMS} items. Unpin one first.",
        )

    pins.append({
        "kind": data.kind,
        "id": data.id,
        "pinned_at": datetime.now(timezone.utc).isoformat(),
    })
    current_user.pinned_items = pins
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)
    return await _hydrate_pins(db, current_user)


@router.delete("/me/pins/{kind}/{item_id}", status_code=204)
async def remove_pin(
    kind: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pins = list(current_user.pinned_items or [])
    new_pins = [
        p
        for p in pins
        if not (
            isinstance(p, dict) and p.get("kind") == kind and p.get("id") == item_id
        )
    ]
    if len(new_pins) == len(pins):
        raise HTTPException(status_code=404, detail="Pin not found")
    current_user.pinned_items = new_pins or None
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()


# ─── Team activity sharing toggle ─────────────────────────────────────────


@router.put("/me/share-activity-with-team", response_model=UserResponse)
async def update_share_activity(
    data: ShareActivityRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.share_activity_with_team = data.share
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)
    return _user_to_response(current_user)
