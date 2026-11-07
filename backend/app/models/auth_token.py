"""One-time auth tokens — password reset and email verification.

Same shape, different purposes — distinguished by `kind` so we don't need
two tables. Tokens hash + salt is overkill for short-lived single-use
codes that we generate ourselves; the URL-safe random ID is the secret.
"""

import secrets
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from app.models.base import Base
from app.models.mixins import TimestampMixin


def _make_token() -> str:
    """44-char URL-safe random string (256 bits of entropy)."""
    return secrets.token_urlsafe(32)


def _default_expiry() -> datetime:
    """1-hour validity window for new tokens. Caller can override in the route."""
    return datetime.now(timezone.utc) + timedelta(hours=1)


class AuthToken(Base, TimestampMixin):
    __tablename__ = "auth_tokens"

    id = sa.Column(sa.String, primary_key=True, default=_make_token)
    user_id = sa.Column(
        sa.String,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 'password_reset' | 'email_verify'. Restrict at the route layer rather
    # than via DB constraint so adding a new kind doesn't require a migration.
    kind = sa.Column(sa.String, nullable=False, index=True)
    expires_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, default=_default_expiry
    )
    used_at = sa.Column(sa.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        sa.Index("ix_auth_tokens_user_kind", "user_id", "kind"),
    )
