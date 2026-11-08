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
    # One of: "full" (default, the existing detail layout), "executive_summary"
    # (1-page condensed), "comparison" (multi-source), "institutional_audit"
    # (multi-researcher). Frontend picks; renderer dispatches on this.
    template = sa.Column(sa.String, nullable=False, server_default="full")
    # Per-report user notes appended at the top of the rendered PDF. Shape:
    # list of {author_name, text, created_at: iso}.
    annotations = sa.Column(sa.JSON, nullable=True)
    # When the report represents multiple underlying records (comparison,
    # institutional_audit), source_check_id and researcher_profile_id stay
    # NULL and we use these arrays instead. Single-source/researcher reports
    # leave these NULL and use the existing scalar FKs.
    source_check_ids = sa.Column(sa.JSON, nullable=True)
    researcher_profile_ids = sa.Column(sa.JSON, nullable=True)
