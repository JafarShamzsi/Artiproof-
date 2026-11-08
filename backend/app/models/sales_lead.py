"""Institution-tier sales inquiry record.

Separate table from ``users`` because the inquirer might never become
a customer — they could be a dean evaluating tools, a procurement
officer doing due diligence, or a researcher who never signs up.

Most rows have NULL ``user_id`` (cold lead). When an inquiry comes
from a logged-in user we link it so support can see "this user is
already a customer; they want to talk about the team tier".
"""

import sqlalchemy as sa

from app.models.base import Base


class SalesLead(Base):
    __tablename__ = "sales_leads"

    id = sa.Column(sa.String, primary_key=True)
    email = sa.Column(sa.String, nullable=False, index=True)
    name = sa.Column(sa.String, nullable=False)
    institution = sa.Column(sa.String, nullable=True)
    team_size = sa.Column(sa.String, nullable=True)
    message = sa.Column(sa.String, nullable=True)
    user_id = sa.Column(
        sa.String,
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("NOW()"),
        index=True,
    )
