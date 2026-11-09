"""user: 2FA + email verification + linked providers + analysis prefs;
new sessions and auth_tokens tables.

Settings phase 2 — security, sessions, connected accounts, analysis defaults.

User columns added:
- email_verified_at: NULL = unverified. Existing users grandfathered to
  COALESCE(updated_at, created_at, NOW()) so the verification banner
  doesn't appear retroactively.
- totp_secret / totp_enabled / totp_backup_codes: 2FA state. The secret
  is plaintext — encryption-at-rest belongs in a separate KMS rollout
  (column gets transparently re-encrypted at migration time).
- linked_providers (JSON): map of provider name -> { sub, email, linked_at }.
  Backfilled from existing Google sign-ins by inspecting whether
  hashed_password is NULL (Google-only accounts) — but we don't know the
  Google sub from this side, so legacy Google-only users get an empty map
  and re-link on next sign-in (auth router will detect + record).
- analysis_preferences (JSON): per-user defaults for the analysis pipelines.

New tables:
- sessions: one row per JWT issued (after this migration); jti claim links
  back to id. Lets users see their devices and revoke individually.
- auth_tokens: short-lived single-use tokens for password reset + email
  verification. `kind` distinguishes; same TTL story for both.

All new columns nullable / default'd to keep this migration zero-downtime.

Revision ID: 0005_security_sessions
Revises: 0004_user_tier_locale
Create Date: 2026-05-09
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_security_sessions"
down_revision = "0004_user_tier_locale"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- User column additions ---------------------------------------------
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("totp_secret", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "totp_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("users", sa.Column("totp_backup_codes", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("linked_providers", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("analysis_preferences", sa.JSON(), nullable=True))

    # Grandfather existing accounts to "verified" so we don't blast them
    # with a banner on next login. New signups (email_verified_at NULL after
    # this point) follow the verify flow.
    op.execute(
        "UPDATE users SET email_verified_at = COALESCE(updated_at, created_at, NOW()) "
        "WHERE email_verified_at IS NULL"
    )

    # --- Sessions table ----------------------------------------------------
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_revoked_at", "sessions", ["revoked_at"])

    # --- One-time auth tokens ---------------------------------------------
    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_auth_tokens_user_id", "auth_tokens", ["user_id"])
    op.create_index("ix_auth_tokens_kind", "auth_tokens", ["kind"])
    op.create_index("ix_auth_tokens_user_kind", "auth_tokens", ["user_id", "kind"])


def downgrade() -> None:
    op.drop_index("ix_auth_tokens_user_kind", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_kind", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_user_id", table_name="auth_tokens")
    op.drop_table("auth_tokens")

    op.drop_index("ix_sessions_revoked_at", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")

    op.drop_column("users", "analysis_preferences")
    op.drop_column("users", "linked_providers")
    op.drop_column("users", "totp_backup_codes")
    op.drop_column("users", "totp_enabled")
    op.drop_column("users", "totp_secret")
    op.drop_column("users", "email_verified_at")
