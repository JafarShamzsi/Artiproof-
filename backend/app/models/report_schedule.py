"""ReportSchedule — recurring report generation per user.

A daily Celery beat sweep walks active schedules, generates reports for
ones whose `next_run_at <= now`, then advances `next_run_at` by the
schedule's frequency. Email delivery of generated reports is gated on
SMTP infrastructure (not wired yet) — for now the user just sees them
in their /reports list, same as manually generated ones.
"""

import uuid

import sqlalchemy as sa

from app.models.base import Base
from app.models.mixins import TimestampMixin


class ReportSchedule(Base, TimestampMixin):
    __tablename__ = "report_schedules"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = sa.Column(
        sa.String,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # "weekly" | "monthly" — Pydantic literal at the route boundary.
    frequency = sa.Column(sa.String, nullable=False)
    # Template for the generated report — same set as Report.template.
    template = sa.Column(sa.String, nullable=False, server_default="executive_summary")
    # Active schedules are eligible for the daily sweep. Setting to false
    # is a soft-pause; deletion is a hard delete via DELETE /me/report-schedules/{id}.
    active = sa.Column(sa.Boolean, nullable=False, server_default="true", index=True)
    last_run_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    next_run_at = sa.Column(sa.DateTime(timezone=True), nullable=False, index=True)
