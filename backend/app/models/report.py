import uuid
import secrets
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from app.models.base import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


# Share-link TTL. Tokens themselves are unguessable (32-byte urlsafe), but
# the audit flagged that they never expire — a leaked link from a year ago
# is still live. Default 90 days; the owner can rotate via the endpoint.
SHARE_TOKEN_TTL_DAYS = 90


def _default_share_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=SHARE_TOKEN_TTL_DAYS)


class Report(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "reports"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = sa.Column(sa.String, sa.ForeignKey("users.id"), nullable=False, index=True)
    # Org-scoping — see SourceCheck.organization_id for the contract.
    organization_id = sa.Column(
        sa.String, sa.ForeignKey("organizations.id"), nullable=True, index=True
    )
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
    # When the share link stops working. NULL means "never" only on legacy
    # rows from before this column existed (the migration backfills with
    # created_at + 90 days so every row should have a value).
    share_expires_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=True,
        default=_default_share_expires_at,
    )

    __table_args__ = (
        sa.Index("ix_reports_user_id_created_at", "user_id", "created_at"),
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
