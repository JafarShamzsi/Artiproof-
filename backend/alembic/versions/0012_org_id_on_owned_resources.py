"""org_id FK on source_checks, researcher_profiles, reports

Adds a nullable ``organization_id`` foreign key + supporting index to
the three "owned resource" tables, and backfills it from
``users.organization_id`` for rows already in the table.

The audit (May 2026) called out that team-tier shared visibility was
structurally impossible: every owned resource carried only ``user_id``
and no ``organization_id``, so an org admin couldn't query their team's
analyses. Adding the column now keeps the routing layer additive — the
existing ``user_id == current_user.id`` checks still work — while
unblocking the "team view" surface area in a follow-up.

Backfill semantics:
- Free / pro users get NULL (their resources stay private to the user).
- Team users with a non-null users.organization_id at migration time
  get that org id propagated to all their pre-existing rows. New rows
  inserted after this migration must propagate at the route layer; the
  ON CONFLICT-style trigger pattern would couple DB to business rules
  that change.

Zero-downtime: every column is nullable with no default change, the
backfill is a single ``UPDATE`` per table, and the index is created
inside the migration (not CONCURRENTLY — acceptable for these table
sizes). For a very large prod table swap to CONCURRENTLY out-of-band
+ ``alembic stamp``; see backend/alembic/README.md.

Revision ID: 0012_org_id_owned
Revises: 0011_perf_indexes
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_org_id_owned"
down_revision = "0011_perf_indexes"
branch_labels = None
depends_on = None


_TABLES = ("source_checks", "researcher_profiles", "reports")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "organization_id",
                sa.String(),
                sa.ForeignKey("organizations.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(
            f"ix_{table}_organization_id",
            table,
            ["organization_id"],
        )
        # Backfill: propagate the owner's org_id onto pre-existing rows.
        # SET NULL semantics on the FK mean a future org deletion won't
        # cascade-delete history, just unscope it from team views.
        op.execute(
            f"""
            UPDATE {table} AS t
               SET organization_id = u.organization_id
              FROM users AS u
             WHERE t.user_id = u.id
               AND u.organization_id IS NOT NULL
               AND t.organization_id IS NULL
            """
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        op.drop_column(table, "organization_id")
