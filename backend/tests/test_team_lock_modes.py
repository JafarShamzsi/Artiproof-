"""Compile the actual helper queries, not a hand-written replacement query.

These regressions prove SQL spelling and fixture validity, not PostgreSQL
conflict behavior. The opt-in HTTP/FK races exercise that separately.
"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.schemas.org_member import OrgMemberInvite
from app.services.team_invites import lock_org, lock_user
from tests.test_team_consent_integration import INVITE_RACE_EMAIL


@pytest.mark.asyncio
@pytest.mark.parametrize("helper,table", [(lock_user, "users"), (lock_org, "organizations")])
async def test_parent_serialization_locks_exclude_writers_but_allow_fk_key_share(helper, table):
    captured = []
    row = SimpleNamespace(id="synthetic-id")
    class Session:
        async def execute(self, query):
            captured.append(query)
            return SimpleNamespace(scalar_one_or_none=lambda: row)
    assert await helper(Session(), row.id) is row
    query, = captured
    compiled = str(query.compile(dialect=postgresql.dialect()))
    assert f"FROM {table}" in compiled
    # NO KEY UPDATE still conflicts with another NO KEY UPDATE/UPDATE, but
    # unlike UPDATE it is compatible with FK checks' KEY SHARE (PG16 13.3).
    assert compiled.endswith(" FOR NO KEY UPDATE"), compiled
    assert query.get_execution_options()["populate_existing"] is True


def test_hosted_invite_race_payload_passes_real_email_validation():
    assert str(OrgMemberInvite(email=INVITE_RACE_EMAIL).email) == INVITE_RACE_EMAIL
    # Fix the fixture, never weaken the production EmailStr validator.
    with pytest.raises(ValidationError):
        OrgMemberInvite(email="new@integration.invalid")
