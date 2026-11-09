"""Cross-org-aware ownership checks.

The original ownership pattern was a single equality:

    if resource.user_id != current_user.id: 403

That was correct when every resource was personal. After migration 0012
added ``organization_id`` to source_checks, researcher_profiles, and
reports, team-tier admins should be able to read their team's work even
when they aren't the row's ``user_id`` — and Phase C makes that work.

This module centralises the rule. ``_is_org_admin(user)`` reads the
role resolved by ``get_current_user`` (which stashes it on the User
instance as ``_org_role``). That keeps the helper synchronous and lets
all 24 router call sites stay unchanged.

Usage:

    from app.utils.ownership import is_owner_or_org_admin

    if not is_owner_or_org_admin(current_user, profile):
        raise HTTPException(status_code=403, detail="…")
"""

from __future__ import annotations

from typing import Protocol


class _OrgScoped(Protocol):
    """Shape every resource we gate on must satisfy.

    ``user_id`` is mandatory (every row in the soft-delete pattern has
    an owner); ``organization_id`` is optional on the model side but
    referenced by name here. None means the resource is not org-shared.
    """

    user_id: str
    organization_id: str | None


class _UserLike(Protocol):
    id: str
    organization_id: str | None


def _is_org_admin(user: _UserLike) -> bool:
    """True iff the user is an admin of their primary organization.

    Reads the ``_org_role`` attribute that ``get_current_user`` stashes
    on the User instance after loading their membership row. Falls back
    to ``False`` for anything that didn't go through the dependency
    (tests using bare SimpleNamespace, background tasks, etc) — that
    matches the previous "no org admin" default.
    """
    return getattr(user, "_org_role", None) == "admin"


def is_owner_or_org_admin(user: _UserLike, resource: _OrgScoped) -> bool:
    """Return ``True`` if ``user`` is allowed to access ``resource``.

    Two paths to access:

    1. Direct ownership — ``resource.user_id == user.id``.
    2. Org-admin override — both rows have the same non-NULL
       ``organization_id`` AND the user is an org admin of that org.

    Members (non-admin) of the same org get path 1 only; this avoids
    a member seeing org admin's private notes / personal experiments.
    Phase D may add a "member can read all org data" tier; the helper
    is the single place that would change.
    """
    if resource.user_id == user.id:
        return True
    # Org-admin path: both must agree on a non-NULL org, and the user
    # must hold the admin role in that org.
    org_id = getattr(resource, "organization_id", None)
    if org_id is None or user.organization_id != org_id:
        return False
    return _is_org_admin(user)
