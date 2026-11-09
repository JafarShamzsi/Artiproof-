"""Cross-org ownership helper.

Pure-function tests against ``app.utils.ownership.is_owner_or_org_admin``
— no DB, no FastAPI. The helper is the chokepoint for the 28+ ownership
checks across the source-check, researcher, and reports routers, so a
regression here corrupts authorisation everywhere.

Until Phase C adds an ``organization_members`` table, ``_is_org_admin``
stubs to ``False``. The Phase-A contract being pinned here:

    - Owner of a row: always allowed.
    - Non-owner, no org link: never allowed.
    - Non-owner, both rows in the same org: still not allowed today
      (because admin role doesn't resolve yet). Phase C flips this.

The org-admin path is exercised against the real org rule by
monkey-patching the stub, so the structural test ("once a user is
declared admin, they can read a same-org resource") doesn't have to wait
for the migration.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.utils import ownership
from app.utils.ownership import is_owner_or_org_admin


def _user(*, id: str, organization_id: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=id, organization_id=organization_id)


def _resource(*, user_id: str, organization_id: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(user_id=user_id, organization_id=organization_id)


def test_owner_is_always_allowed():
    user = _user(id="u1")
    resource = _resource(user_id="u1")
    assert is_owner_or_org_admin(user, resource) is True


def test_owner_allowed_even_without_org():
    # Ownership beats the org branch — neither side needs an org link.
    user = _user(id="u1", organization_id=None)
    resource = _resource(user_id="u1", organization_id=None)
    assert is_owner_or_org_admin(user, resource) is True


def test_non_owner_no_org_link_denied():
    user = _user(id="u2", organization_id=None)
    resource = _resource(user_id="u1", organization_id=None)
    assert is_owner_or_org_admin(user, resource) is False


def test_non_owner_user_in_org_resource_personal_denied():
    # Resource has no org_id, so even an org admin shouldn't see it.
    user = _user(id="u2", organization_id="org-1")
    resource = _resource(user_id="u1", organization_id=None)
    assert is_owner_or_org_admin(user, resource) is False


def test_non_owner_resource_in_org_user_personal_denied():
    user = _user(id="u2", organization_id=None)
    resource = _resource(user_id="u1", organization_id="org-1")
    assert is_owner_or_org_admin(user, resource) is False


def test_non_owner_different_orgs_denied():
    user = _user(id="u2", organization_id="org-A")
    resource = _resource(user_id="u1", organization_id="org-B")
    assert is_owner_or_org_admin(user, resource) is False


def test_non_owner_same_org_denied_until_phase_c():
    # The Phase A contract: even when both rows share an org, the stub
    # _is_org_admin returns False so behaviour is identical to the old
    # check. Phase C flips this when the role bit lands.
    user = _user(id="u2", organization_id="org-1")
    resource = _resource(user_id="u1", organization_id="org-1")
    assert is_owner_or_org_admin(user, resource) is False


def test_non_owner_same_org_allowed_when_admin_role_resolves(monkeypatch):
    # Simulate Phase C by overriding the stub. The structural rule
    # ("admin + same org ⇒ allowed") is being pinned here so the Phase C
    # upgrade can't accidentally break the org-admin branch.
    monkeypatch.setattr(ownership, "_is_org_admin", lambda u: True)
    user = _user(id="u2", organization_id="org-1")
    resource = _resource(user_id="u1", organization_id="org-1")
    assert is_owner_or_org_admin(user, resource) is True


def test_admin_in_other_org_still_denied(monkeypatch):
    # Admin in org-A should NOT be able to read a resource in org-B.
    monkeypatch.setattr(ownership, "_is_org_admin", lambda u: True)
    user = _user(id="u2", organization_id="org-A")
    resource = _resource(user_id="u1", organization_id="org-B")
    assert is_owner_or_org_admin(user, resource) is False


def test_admin_with_no_org_cannot_match_orgd_resource(monkeypatch):
    # User has admin role but isn't in any org → can't match anything.
    monkeypatch.setattr(ownership, "_is_org_admin", lambda u: True)
    user = _user(id="u2", organization_id=None)
    resource = _resource(user_id="u1", organization_id="org-1")
    assert is_owner_or_org_admin(user, resource) is False


def test_resource_without_org_attr_treated_as_unscoped():
    # getattr defends against forgotten columns. A resource without an
    # organization_id attribute should be denied to non-owners, never
    # accidentally allowed.
    user = _user(id="u2", organization_id="org-1")
    resource = SimpleNamespace(user_id="u1")  # no organization_id
    assert is_owner_or_org_admin(user, resource) is False


# ─── Phase C: real _org_role contract ──────────────────────────────────────


def test_user_with_org_role_admin_reads_org_resource():
    # The real Phase C path: User instance carries ``_org_role``
    # (stashed by get_current_user). Helper reads it without DB.
    user = _user(id="u2", organization_id="org-1")
    user._org_role = "admin"
    resource = _resource(user_id="u1", organization_id="org-1")
    assert is_owner_or_org_admin(user, resource) is True


def test_user_with_org_role_member_cannot_read_other_member_resource():
    # Members get path-1 (direct ownership) only; non-admin in the same
    # org doesn't see another member's row. Phase D may change this.
    user = _user(id="u2", organization_id="org-1")
    user._org_role = "member"
    resource = _resource(user_id="u1", organization_id="org-1")
    assert is_owner_or_org_admin(user, resource) is False


def test_user_without_org_role_attr_treated_as_no_role():
    # SimpleNamespace without _org_role (the legacy test shape) keeps
    # working — the helper falls back to the conservative "no role".
    user = _user(id="u2", organization_id="org-1")
    resource = _resource(user_id="u1", organization_id="org-1")
    assert is_owner_or_org_admin(user, resource) is False
