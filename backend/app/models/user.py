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
