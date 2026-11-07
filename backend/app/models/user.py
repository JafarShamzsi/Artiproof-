import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM
from app.models.base import Base

# Prisma creates this PostgreSQL ENUM — reference it, don't recreate
user_role_enum = ENUM("researcher", "faculty", "admin", name="UserRole", create_type=False)


def _utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = sa.Column(sa.String, unique=True, nullable=False, index=True)
    hashed_password = sa.Column(sa.String, nullable=True)
    full_name = sa.Column(sa.String, nullable=False)
    institution = sa.Column(sa.String, nullable=True)
    role = sa.Column(user_role_enum, nullable=False, server_default="researcher")
    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at = sa.Column(sa.DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)
