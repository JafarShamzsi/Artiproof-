"""Single chokepoint for writing ``organization_audit_logs`` rows.

Pattern mirrors ``services/billing/tier_change.py``: every org-management
endpoint goes through this helper so the audit trail can never drift
from reality. A new endpoint added later that mutates org state without
calling ``record_org_action`` is the failure mode this design exists to
catch in code review.

Caller is responsible for committing. We add to the session but don't
commit, so an endpoint that fails downstream rolls back the audit row
along with its primary mutation.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization_audit_log import OrganizationAuditLog

logger = logging.getLogger(__name__)


# The canonical action vocabulary — keep this list in sync with the docs
# in models/organization_audit_log.py. The string is what's stored.
ORG_ACTIONS = frozenset(
    {
        "org_created",
        "invite_sent",
        "invite_resent",
        "invite_revoked",
        "member_added",
        "member_removed",
        "role_changed",
        "seat_limit_changed",
        "org_settings_changed",
    }
)


async def record_org_action(
    *,
    db: AsyncSession,
    org_id: str,
    actor_user_id: Optional[str],
    action: str,
    target_user_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> OrganizationAuditLog:
    """Append one audit row + emit a structured log line.

    Does NOT commit — the calling endpoint is expected to ``await
    db.commit()`` after its own mutations have succeeded so an audit
    row never outlives a rolled-back primary mutation.
    """
    if action not in ORG_ACTIONS:
        # Don't 500 the request — but loudly flag the developer error so
        # it's caught in tests. Insert the row anyway so we don't lose
        # the trail; review will rename the action to the canonical one.
        logger.error("org_audit: unknown action=%s — proceeding anyway", action)

    row = OrganizationAuditLog(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        actor_user_id=actor_user_id,
        action=action,
        target_user_id=target_user_id,
        payload=payload or {},
    )
    db.add(row)

    # Parallel structured log line for log-based alerting and grep.
    logger.info(
        "org_audit",
        extra={
            "org_id": org_id,
            "actor_user_id": actor_user_id,
            "action": action,
            "target_user_id": target_user_id,
            "payload": payload or {},
        },
    )
    return row
