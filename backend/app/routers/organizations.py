"""Organization-scoped endpoints — currently white-label branding only.

Branding is gated on `tier='team'` and the user belonging to the org.
Anyone in the org can read; only the user themselves changing their own
org's branding requires the team tier (no per-org admin role yet — to be
introduced when team membership becomes self-serve)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.report import OrganizationBranding, OrganizationBrandingResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/organizations", tags=["Organizations"])


def _response(o: Organization) -> OrganizationBrandingResponse:
    return OrganizationBrandingResponse(
        id=o.id,
        name=o.name,
        logo_url=o.logo_url,
        primary_color=o.primary_color,
        secondary_color=o.secondary_color,
    )


async def _require_org_member(
    org_id: str, current_user: User, db: AsyncSession
) -> Organization:
    if current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.get("/{org_id}/branding", response_model=OrganizationBrandingResponse)
async def get_org_branding(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = await _require_org_member(org_id, current_user, db)
    return _response(org)


@router.put("/{org_id}/branding", response_model=OrganizationBrandingResponse)
async def update_org_branding(
    org_id: str,
    data: OrganizationBranding,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update logo + colors. Team-tier only. Until org-admin roles exist,
    any team-tier member of the org can edit branding."""
    if current_user.tier != "team":
        raise HTTPException(
            status_code=403, detail="White-label branding requires the team tier"
        )
    org = await _require_org_member(org_id, current_user, db)
    org.logo_url = data.logo_url
    org.primary_color = data.primary_color
    org.secondary_color = data.secondary_color
    await db.commit()
    await db.refresh(org)
    return _response(org)
