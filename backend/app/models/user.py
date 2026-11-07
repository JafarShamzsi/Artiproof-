import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

from app.models.base import Base
from app.models.mixins import TimestampMixin

# Prisma created the UserRole enum type. Reference it without re-creating.
user_role_enum = ENUM("researcher", "faculty", "admin", name="UserRole", create_type=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = sa.Column(sa.String, unique=True, nullable=False, index=True)
    hashed_password = sa.Column(sa.String, nullable=True)
    full_name = sa.Column(sa.String, nullable=False)
    institution = sa.Column(sa.String, nullable=True)
    role = sa.Column(user_role_enum, nullable=False, server_default="researcher")
