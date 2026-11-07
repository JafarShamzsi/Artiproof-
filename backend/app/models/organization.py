"""Organization — the unit of "team" identity.

Existence is required for tier='team' users to use team activity features.
For now organizations are seeded out-of-band (admin script / DB seed); a
user-facing invite + admin UI for membership is a separate phase.
"""

import uuid

import sqlalchemy as sa

from app.models.base import Base
from app.models.mixins import TimestampMixin


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = sa.Column(sa.String, nullable=False)
    # Optional human-readable slug for URL generation later. Unique when set.
    slug = sa.Column(sa.String, nullable=True, unique=True)
