"""Durable analysis intent, execution ownership and replayable progress."""

import uuid

import sqlalchemy as sa

from app.models.base import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = sa.Column(sa.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    kind = sa.Column(sa.String(32), nullable=False)
    resource_id = sa.Column(sa.String, nullable=False)
    user_id = sa.Column(sa.String, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = sa.Column(sa.String(16), nullable=False, server_default="queued")
    owner_token = sa.Column(sa.String(64), nullable=True)
    attempts = sa.Column(sa.Integer, nullable=False, server_default="0")
    max_attempts = sa.Column(sa.Integer, nullable=False, server_default="3")
    lease_expires_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    next_dispatch_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    dispatch_count = sa.Column(sa.Integer, nullable=False, server_default="0")
    prior_revision = sa.Column(sa.JSON, nullable=True)
    error_code = sa.Column(sa.String(80), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    started_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    completed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        sa.CheckConstraint("kind IN ('source_check', 'researcher')", name="kind_values"),
        sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed', 'cancelled')", name="status_values"),
        sa.CheckConstraint("attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts", name="attempt_bounds"),
        sa.Index("ix_analysis_runs_dispatch", "status", "next_dispatch_at"),
        sa.Index("ix_analysis_runs_lease", "status", "lease_expires_at"),
        sa.Index("uq_analysis_runs_active_resource", "kind", "resource_id", unique=True,
                 postgresql_where=sa.text("status IN ('queued', 'running')")),
    )


class AnalysisRunEvent(Base):
    __tablename__ = "analysis_run_events"

    id = sa.Column(sa.BigInteger, sa.Identity(), primary_key=True)
    run_id = sa.Column(sa.String, sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    event_type = sa.Column(sa.String(64), nullable=False)
    payload = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())

    __table_args__ = (sa.Index("ix_analysis_run_events_replay", "run_id", "id"),)
