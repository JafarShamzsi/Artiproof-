import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

from app.models.base import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin

# Prisma created the UserRole enum type. Reference it without re-creating.
user_role_enum = ENUM("researcher", "faculty", "admin", name="UserRole", create_type=False)


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = sa.Column(sa.String, unique=True, nullable=False, index=True)
    hashed_password = sa.Column(sa.String, nullable=True)
    full_name = sa.Column(sa.String, nullable=False)
    institution = sa.Column(sa.String, nullable=True)
    role = sa.Column(user_role_enum, nullable=False, server_default="researcher")
    # Plan tier — see app.constants.TIER_LIMITS for quotas.
    tier = sa.Column(sa.String, nullable=False, server_default="free", index=True)
    # Per-user notification toggles. Merged with DEFAULT_NOTIFICATION_PREFERENCES on read
    # so adding a new key doesn't require a backfill of existing rows.
    notification_preferences = sa.Column(sa.JSON, nullable=True)
    # ISO 639-1 code from constants.SUPPORTED_LOCALES. Persists the user's
    # chosen UI language; actual content translation is handled separately.
    locale = sa.Column(sa.String(8), nullable=False, server_default="en")
    # When set, the account is suspended — get_current_user blocks all routes
    # except /api/auth/reactivate. User can self-reactivate. Distinct from
    # `deleted_at` (account deletion).
    deactivated_at = sa.Column(sa.DateTime(timezone=True), nullable=True, index=True)
    # Email verification: NULL = unverified. Migration 0005 grandfathers existing
    # users to created_at so they don't see a verification banner retroactively.
    email_verified_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    # TOTP shared secret. Stored plaintext for now — encryption-at-rest is a
    # KMS concern noted in the migration. Only populated after 2FA setup.
    totp_secret = sa.Column(sa.String, nullable=True)
    totp_enabled = sa.Column(sa.Boolean, nullable=False, server_default="false")
    # JSON list of bcrypt-hashed backup codes. Each single-use; consuming one
    # rotates the array (drops the matched hash) before responding.
    totp_backup_codes = sa.Column(sa.JSON, nullable=True)
    # OAuth providers linked to this account. Shape:
    #   {"google": {"sub": str, "email": str, "linked_at": iso8601}}
    linked_providers = sa.Column(sa.JSON, nullable=True)
    # Per-user defaults for analysis pipelines. Merged with
    # constants.DEFAULT_ANALYSIS_PREFERENCES on read.
    analysis_preferences = sa.Column(sa.JSON, nullable=True)
