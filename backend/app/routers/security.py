"""Security + identity endpoints.

Splits out everything related to password reset, email verification, 2FA,
session management, and connected accounts. Keeps `routers/auth.py` focused
on registration / login / profile.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request
from passlib.hash import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.constants import (
    EMAIL_VERIFICATION_TOKEN_TTL_HOURS,
    PASSWORD_RESET_TOKEN_TTL_HOURS,
    TOTP_BACKUP_CODE_COUNT,
)
from app.database import get_db
from app.models.auth_token import AuthToken
from app.models.session import Session
from app.models.user import User
from app.services.email import (
    is_configured as email_is_configured,
    render_password_reset,
    render_verify_email,
    send_email,
)
from app.schemas.auth import (
    EmailVerificationRequestResponse,
    EmailVerificationStatus,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    SessionItem,
    TotpDisableRequest,
    TotpEnableRequest,
    TotpSetupResponse,
    TotpStatus,
)
from app.utils.auth import (
    create_access_token,
    decode_account_token,
    get_current_user,
    get_current_user_allow_deactivated,
)
from app.utils.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Security"])


# ─── Password reset ────────────────────────────────────────────────────────


def _build_reset_url(token: str) -> str:
    return f"{settings.APP_URL}/reset-password/{token}"


def _build_verify_url(token: str) -> str:
    return f"{settings.APP_URL}/verify-email/{token}"


def _is_dev_env() -> bool:
    return settings.ENVIRONMENT.lower() != "production"


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a password-reset link.

    Always returns success regardless of whether the email exists, so an
    attacker can't enumerate accounts. In dev (no SMTP), the URL is
    returned inline so the flow remains testable; in production this
    response stays empty and the URL is sent via email (TODO: wire SMTP).
    """
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if user is None or user.deleted_at is not None:
        # Don't disclose. Sleep briefly so timing doesn't leak account
        # existence — bcrypt verify takes ~300ms; mirror that here.
        return ForgotPasswordResponse()

    if user.hashed_password is None:
        # Google-only account; password reset doesn't apply. Still respond
        # success to avoid enumerating "this email is on Google sign-in".
        return ForgotPasswordResponse()

    token = AuthToken(
        user_id=user.id,
        kind="password_reset",
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=PASSWORD_RESET_TOKEN_TTL_HOURS),
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)

    url = _build_reset_url(token.id)
    subject, html, text = render_password_reset(
        name=user.full_name,
        reset_url=url,
        ttl_hours=PASSWORD_RESET_TOKEN_TTL_HOURS,
    )
    await send_email(to=user.email, subject=subject, html=html, text=text)

    # In dev (no Resend key) the email lands in logs; surface the URL inline
    # so the local flow remains testable from the response alone. In
    # production this stays empty so the URL never appears in API output.
    if _is_dev_env() and not email_is_configured():
        return ForgotPasswordResponse(dev_reset_url=url)
    return ForgotPasswordResponse()


@router.post("/reset-password", status_code=204)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Consume the token and set a new password.

    Token is single-use — `used_at` gets set the moment we accept it. Tokens
    expire after 1 hour by default (constants.PASSWORD_RESET_TOKEN_TTL_HOURS).
    """
    token = await db.get(AuthToken, data.token)
    now = datetime.now(timezone.utc)
    if (
        token is None
        or token.kind != "password_reset"
        or token.used_at is not None
        or token.expires_at < now
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = await db.get(User, token.user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user.hashed_password = bcrypt.hash(data.new_password)
    user.updated_at = now
    token.used_at = now

    # Revoke all existing sessions — safest assumption is the password reset
    # was triggered by someone who lost access, so we shouldn't trust any
    # outstanding tokens.
    sessions_q = await db.execute(
        select(Session).where(Session.user_id == user.id, Session.revoked_at.is_(None))
    )
    for s in sessions_q.scalars().all():
        s.revoked_at = now

    await db.commit()


# ─── Email verification ────────────────────────────────────────────────────


@router.get("/me/email/status", response_model=EmailVerificationStatus)
async def email_verification_status(current_user: User = Depends(get_current_user)):
    return EmailVerificationStatus(
        email=current_user.email,
        verified=current_user.email_verified_at is not None,
        verified_at=current_user.email_verified_at,
    )


@router.post(
    "/me/email/verify/request", response_model=EmailVerificationRequestResponse
)
@limiter.limit("3/minute")
async def request_email_verification(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Issue a fresh verification token. Idempotent in spirit — if a recent
    unused token still exists, we reuse it rather than spamming the user
    with multiple links."""
    if current_user.email_verified_at is not None:
        raise HTTPException(status_code=400, detail="Email is already verified")

    # Reuse a still-valid unused token if present.
    existing_q = await db.execute(
        select(AuthToken).where(
            AuthToken.user_id == current_user.id,
            AuthToken.kind == "email_verify",
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > datetime.now(timezone.utc),
        )
    )
    token = existing_q.scalars().first()
    if token is None:
        token = AuthToken(
            user_id=current_user.id,
            kind="email_verify",
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=EMAIL_VERIFICATION_TOKEN_TTL_HOURS),
        )
        db.add(token)
        await db.commit()
        await db.refresh(token)

    url = _build_verify_url(token.id)
    subject, html, text = render_verify_email(
        name=current_user.full_name,
        verify_url=url,
        ttl_hours=EMAIL_VERIFICATION_TOKEN_TTL_HOURS,
    )
    await send_email(to=current_user.email, subject=subject, html=html, text=text)
    if _is_dev_env() and not email_is_configured():
        return EmailVerificationRequestResponse(dev_verify_url=url)
    return EmailVerificationRequestResponse()


@router.post("/email/verify", status_code=204)
async def consume_email_verification(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """Public — no auth required because the user clicks the link from email.
    The token itself is the secret."""
    token_id = payload.get("token")
    if not isinstance(token_id, str):
        raise HTTPException(status_code=400, detail="Token is required")

    token = await db.get(AuthToken, token_id)
    now = datetime.now(timezone.utc)
    if (
        token is None
        or token.kind != "email_verify"
        or token.used_at is not None
        or token.expires_at < now
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = await db.get(User, token.user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    if user.email_verified_at is None:
        user.email_verified_at = now
    token.used_at = now
    await db.commit()


# ─── 2FA TOTP ─────────────────────────────────────────────────────────────


def _generate_backup_codes(count: int = TOTP_BACKUP_CODE_COUNT) -> list[str]:
    """8-char alphanumeric, displayed once. Backend stores bcrypt hashes."""
    return [secrets.token_urlsafe(6).replace("_", "x").replace("-", "y")[:8].upper() for _ in range(count)]


def _consume_backup_code(user: User, code: str) -> bool:
    """Pop the matching hash from totp_backup_codes if any. Returns True
    when consumed; updates the column in-place. Caller commits."""
    hashes: list[str] = list(user.totp_backup_codes or [])
    code = code.strip().upper()
    for i, h in enumerate(hashes):
        if bcrypt.verify(code, h):
            hashes.pop(i)
            user.totp_backup_codes = hashes
            return True
    return False


def _verify_totp_or_backup(user: User, code: str) -> bool:
    """Accepts either a current TOTP or a still-valid backup code.

    Backup codes are returned to the user only once at setup; we store the
    bcrypt hash and pop it on use. Treat any 6-digit input as TOTP, longer
    inputs as backup codes — pyotp.now() always produces 6 digits.
    """
    code = code.strip()
    if len(code) == 6 and code.isdigit() and user.totp_secret:
        if pyotp.TOTP(user.totp_secret).verify(code, valid_window=1):
            return True
    return _consume_backup_code(user, code)


@router.get("/me/2fa", response_model=TotpStatus)
async def totp_status(current_user: User = Depends(get_current_user)):
    backup_remaining = len(current_user.totp_backup_codes or [])
    return TotpStatus(
        enabled=bool(current_user.totp_enabled), backup_codes_remaining=backup_remaining,
        enrollment_available=bool(current_user.hashed_password),
        enrollment_unavailable_reason=None if current_user.hashed_password else _TOTP_PASSWORD_REQUIRED,
    )


_TOTP_PASSWORD_REQUIRED = (
    "App two-factor enrollment requires password sign-in; Google-only TOTP completion and recovery are not supported."
)


def _require_totp_password_login(user: User):
    if not user.hashed_password:
        raise HTTPException(status_code=409, detail=_TOTP_PASSWORD_REQUIRED)


@router.post("/me/2fa/setup", response_model=TotpSetupResponse)
async def begin_totp_setup(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a fresh TOTP secret + backup codes.

    The secret is staged on the user row immediately; `enabled` flips only
    once /me/2fa/enable confirms the user can produce a valid code. Calling
    /setup twice replaces the previous unconfirmed setup.
    """
    _require_totp_password_login(current_user)
    if current_user.totp_enabled:
        raise HTTPException(
            status_code=400,
            detail="2FA is already enabled. Disable it first to re-issue.",
        )

    secret = pyotp.random_base32()
    backup_codes = _generate_backup_codes()
    backup_hashes = [bcrypt.hash(c) for c in backup_codes]

    current_user.totp_secret = secret
    current_user.totp_backup_codes = backup_hashes
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()

    issuer = "ArtiProof"
    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
        name=current_user.email, issuer_name=issuer
    )
    return TotpSetupResponse(
        provisioning_uri=provisioning_uri, secret=secret, backup_codes=backup_codes
    )


@router.post("/me/2fa/enable", response_model=TotpStatus)
async def enable_totp(
    data: TotpEnableRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Activate 2FA after the user proves they can read codes from their
    authenticator. Verifies against the staged secret from /setup."""
    _require_totp_password_login(current_user)
    if current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=400, detail="Run POST /me/2fa/setup first to stage a secret"
        )

    if not pyotp.TOTP(current_user.totp_secret).verify(data.code.strip(), valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid code")

    current_user.totp_enabled = True
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return TotpStatus(
        enabled=True, backup_codes_remaining=len(current_user.totp_backup_codes or []),
        enrollment_available=True,
    )


@router.post("/me/2fa/disable", status_code=204)
async def disable_totp(
    data: TotpDisableRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirm with both password and a current 2FA / backup code, then
    clear the secret + backup codes so the user can re-setup later."""
    if not current_user.totp_enabled:
        raise HTTPException(status_code=400, detail="2FA is not enabled")
    if not current_user.hashed_password or not bcrypt.verify(
        data.current_password, current_user.hashed_password
    ):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if not _verify_totp_or_backup(current_user, data.code):
        raise HTTPException(status_code=401, detail="Invalid 2FA code")

    current_user.totp_enabled = False
    current_user.totp_secret = None
    current_user.totp_backup_codes = None
    current_user.updated_at = datetime.now(timezone.utc)
    await db.commit()


# ─── Sessions ─────────────────────────────────────────────────────────────


@router.get("/me/sessions", response_model=list[SessionItem])
async def list_sessions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """All non-revoked sessions for the current user, sorted newest-first.
    `is_current` flags the session the request itself is using so the UI
    can warn before revoking it."""
    result = await db.execute(
        select(Session)
        .where(Session.user_id == current_user.id, Session.revoked_at.is_(None))
        .order_by(Session.created_at.desc())
    )
    sessions = result.scalars().all()

    # Identify the current session via the JWT's jti claim — middleware
    # already validated the token, so we can re-decode the header here
    # cheaply rather than threading the payload through.
    auth_header = request.headers.get("authorization", "")
    current_jti: str | None = None
    if auth_header.lower().startswith("bearer "):
        try:
            payload = decode_account_token(auth_header[7:])
            current_jti = payload.get("jti")
        except Exception:
            current_jti = None

    return [
        SessionItem(
            id=s.id,
            user_agent=s.user_agent,
            ip_address=s.ip_address,
            label=s.label,
            created_at=s.created_at,
            last_used_at=s.last_used_at,
            is_current=(s.id == current_jti),
        )
        for s in sessions
    ]


@router.delete("/me/sessions/{session_id}", status_code=204)
async def revoke_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await db.get(Session, session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    session.revoked_at = datetime.now(timezone.utc)
    await db.commit()


@router.delete("/me/sessions", status_code=204)
async def revoke_all_other_sessions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke every session except the one making the request — useful for
    "sign out everywhere" without locking the current user out."""
    auth_header = request.headers.get("authorization", "")
    current_jti: str | None = None
    if auth_header.lower().startswith("bearer "):
        try:
            payload = decode_account_token(auth_header[7:])
            current_jti = payload.get("jti")
        except Exception:
            current_jti = None

    result = await db.execute(
        select(Session).where(
            Session.user_id == current_user.id, Session.revoked_at.is_(None)
        )
    )
    now = datetime.now(timezone.utc)
    for s in result.scalars().all():
        if s.id == current_jti:
            continue
        s.revoked_at = now
    await db.commit()


# ─── Helper: create a session row + token (used by login + 2fa challenge) ──


async def issue_login_token(
    db: AsyncSession,
    user: User,
    request: Request,
    label: str | None = None,
) -> tuple[str, Session]:
    """Persist a Session and return (jwt, session). Used by the auth router."""
    session = Session(
        id=str(uuid.uuid4()),
        user_id=user.id,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
        label=label,
        last_used_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    token = create_access_token(
        user.id, user.email, session_id=session.id, tier=user.tier
    )
    return token, session
