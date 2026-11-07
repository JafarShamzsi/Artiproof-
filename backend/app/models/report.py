import uuid
import secrets

import sqlalchemy as sa

from app.models.base import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class Report(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "reports"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = sa.Column(sa.String, sa.ForeignKey("users.id"), nullable=False, index=True)
    source_check_id = sa.Column(sa.String, sa.ForeignKey("source_checks.id", ondelete="SET NULL"), nullable=True)
    researcher_profile_id = sa.Column(sa.String, sa.ForeignKey("researcher_profiles.id", ondelete="SET NULL"), nullable=True)
    report_type = sa.Column(sa.String, nullable=False)  # source_verification, researcher_integrity
    title = sa.Column(sa.String, nullable=False)
    summary = sa.Column(sa.Text, nullable=True)
    pdf_path = sa.Column(sa.String, nullable=True)
    share_token = sa.Column(
        sa.String,
        unique=True,
        nullable=False,
        default=lambda: secrets.token_urlsafe(32),
        index=True,
    )
