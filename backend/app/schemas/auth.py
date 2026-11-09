from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


UserRoleStr = Literal["researcher", "faculty", "admin"]


# bcrypt only hashes the first 72 bytes of UTF-8. Reject longer passwords
# explicitly instead of letting them silently collide with their first 72 bytes.
BCRYPT_MAX_BYTES = 72


def _validate_bcrypt_length(value: str) -> str:
    if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError(
            f"Password must be at most {BCRYPT_MAX_BYTES} bytes (UTF-8). "
            "Note: emoji and accented characters take multiple bytes."
        )
    return value


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    institution: Optional[str] = None
    role: UserRoleStr = "researcher"
    # Optional invite validation only. Joining requires verified email
    # and a separate authenticated recipient acceptance POST.
    invite_token: Optional[str] = None
    # Optional plan intent — captured by the frontend register page
    # from a ``?plan=`` query param. Stored as a tier_change_audits
    # row with reason="signup_intent". DOES NOT change the user's
    # tier; the actual upgrade happens after the payment processor
    # confirms payment. Phase D scaffolding so the future billing
    # wire-up has a "who came in wanting Pro" funnel to measure.
    intent_plan: Optional[str] = None

    @field_validator("password")
    @classmethod
    def _password_within_bcrypt_limit(cls, v: str) -> str:
        return _validate_bcrypt_length(v)


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def _password_within_bcrypt_limit(cls, v: str) -> str:
        return _validate_bcrypt_length(v)


class GoogleLogin(BaseModel):
    id_token: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    institution: Optional[str] = None
    role: str
    tier: str = "free"
    locale: str = "en"
    deactivated_at: Optional[datetime] = None
    created_at: datetime
    # Team-tier privacy toggle. Default true matches the model's server_default
    # so the Settings UI shows "on" before the user changes anything.
    share_activity_with_team: bool = True
    # Surfaced for the Settings page: branding section calls
    # `/api/organizations/{organization_id}/branding` and we need this id
    # client-side. Null for free/pro users.
    organization_id: Optional[str] = None
    # The user's role in their primary org, if any. ``get_current_user``
    # resolves this from organization_members and stashes it on the
    # User instance as ``_org_role``; we surface it here so the Settings
    # UI can conditionally show admin-only controls without a separate
    # round-trip.
    org_role: Optional[str] = None
    # ─── Billing scaffolding (Phase D) ─────────────────────────────────
    # Surfaced so the Settings → Billing section can render the current
    # subscription state badge + next billing date. The processor wires
    # write these via ``apply_tier_change``; UI reads them.
    subscription_state: str = "none"
    next_billing_date: Optional[datetime] = None
    last_billing_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    institution: Optional[str] = None
    role: Optional[UserRoleStr] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _new_password_within_bcrypt_limit(cls, v: str) -> str:
        return _validate_bcrypt_length(v)


class NotificationPreferences(BaseModel):
    """All keys default-true/false to match DEFAULT_NOTIFICATION_PREFERENCES.
    Adding a key here without matching the constant will produce a stable
    response shape (existing rows fall back to defaults), so consumers can
    safely treat new fields as optional.

    `extra='forbid'` rejects unknown keys with a 422 instead of silently
    dropping them — the JSON column is small and we'd rather surface
    typos than persist them as no-op cruft.
    """

    email_on_completion: bool = True
    email_on_low_credibility: bool = True
    email_weekly_digest: bool = False
    email_product_updates: bool = False

    model_config = {"extra": "forbid"}


class LocaleUpdate(BaseModel):
    locale: str  # validated against constants.SUPPORTED_LOCALES in the route


class AccountDeactivateRequest(BaseModel):
    """Confirm with the current password — same UX as deletion."""
    current_password: str


class AccountDeleteRequest(BaseModel):
    """Confirm with the current password and a typed phrase to prevent fat-finger
    deletion from the dashboard. Frontend asks the user to type DELETE."""
    current_password: str
    confirm: str  # must equal "DELETE"


# ─── Password reset ───────────────────────────────────────────────────────


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """Always succeeds — never confirms whether the email exists.
    `dev_reset_url` is populated only when SMTP isn't configured so the dev /
    QA flow remains testable. Production should never see it set."""
    detail: str = "If that account exists, a reset link has been sent."
    dev_reset_url: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _new_password_within_bcrypt_limit(cls, v: str) -> str:
        return _validate_bcrypt_length(v)


# ─── Email verification ──────────────────────────────────────────────────


class EmailVerificationRequestResponse(BaseModel):
    detail: str = "Verification link sent."
    dev_verify_url: Optional[str] = None


class EmailVerificationStatus(BaseModel):
    email: str
    verified: bool
    verified_at: Optional[datetime] = None


# ─── 2FA TOTP ────────────────────────────────────────────────────────────


class TotpSetupResponse(BaseModel):
    """Returned once at setup. The user scans `provisioning_uri` with their
    authenticator and types the 6-digit code into /me/2fa/enable to confirm.
    `backup_codes` are shown ONCE — backend stores hashes, never plaintext.
    """
    provisioning_uri: str
    secret: str  # base32 — for users who can't scan and need to type
    backup_codes: list[str]


class TotpEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)  # 6-digit TOTP, or 8-char backup


class TotpDisableRequest(BaseModel):
    current_password: str
    code: str = Field(min_length=6, max_length=8)


class TotpStatus(BaseModel):
    enabled: bool
    backup_codes_remaining: int = 0
    enrollment_available: bool = False
    enrollment_unavailable_reason: Optional[str] = None


class LoginTwoFactorRequest(BaseModel):
    """Step 2 of login when the user has TOTP enabled. The challenge_token
    came from step 1 and links this submission to the right user."""
    challenge_token: str
    code: str = Field(min_length=6, max_length=8)


class LoginChallengeResponse(BaseModel):
    """Step 1 returns this when the account has 2FA. Frontend stashes the
    challenge_token and POSTs it back with the code to /api/auth/login/2fa."""
    challenge: str = "totp"
    challenge_token: str


# ─── Sessions ────────────────────────────────────────────────────────────


class SessionItem(BaseModel):
    id: str
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    label: Optional[str] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None
    is_current: bool = False  # set by the route handler

    model_config = {"from_attributes": True}


# ─── Connected accounts ──────────────────────────────────────────────────


class ConnectionItem(BaseModel):
    provider: str  # "google" for now
    linked: bool
    email: Optional[str] = None
    linked_at: Optional[datetime] = None


class GoogleLinkRequest(BaseModel):
    id_token: str = Field(min_length=1)


# ─── Analysis preferences ────────────────────────────────────────────────


class AnalysisPreferences(BaseModel):
    """Per-user pipeline defaults. Same shape as constants.DEFAULT_ANALYSIS_PREFERENCES."""

    check_citations: bool = True
    trace_misinfo_origins: bool = True
    ai_detection_model: str = "gemini-2.0-flash"
    researcher_field_inference: bool = True


# ─── Pinned items ────────────────────────────────────────────────────────


PinKindStr = Literal["source_check", "researcher", "report"]


class PinRequest(BaseModel):
    kind: PinKindStr
    id: str = Field(min_length=1, max_length=64)


class PinnedItem(BaseModel):
    """Hydrated pin returned to the dashboard."""

    kind: PinKindStr
    id: str
    title: str
    score: Optional[float] = None
    pinned_at: datetime


# ─── Team activity sharing toggle ────────────────────────────────────────


class ShareActivityRequest(BaseModel):
    share: bool
