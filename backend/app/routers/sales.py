"""Institution-tier lead capture.

The Pricing page's "Institution" CTA points at the ``/contact-sales``
landing route which posts here. Each inquiry lands as a ``sales_leads``
row and (best-effort) emails a notification so support can answer
quickly.

Rate-limited because the form is unauthenticated — the IP bucket is
the only protection against a bot mass-submitting. 5/hour/IP keeps a
real human's form-fill workflow unaffected while blocking trivial
abuse.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.sales_lead import SalesLead
from app.models.user import User
from app.services.email import send_email
from app.utils.auth import get_current_user_optional
from app.utils.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sales", tags=["Sales"])


class SalesInquiry(BaseModel):
    """Body for ``POST /api/sales/inquiry``.

    Everything except email + name is optional so a researcher can drop
    a one-line message without filling a form-burden. ``team_size``
    stays as a string because the surface in the UI is a dropdown of
    ranges (e.g. "1-5", "6-25", "26-100", "100+"), not an integer.
    """

    email: EmailStr
    name: str = Field(..., min_length=1, max_length=200)
    institution: Optional[str] = Field(None, max_length=200)
    team_size: Optional[str] = Field(None, max_length=20)
    message: Optional[str] = Field(None, max_length=4000)


class SalesInquiryResponse(BaseModel):
    """Response shape — minimal on purpose so we don't leak the
    generated id externally. Confirms receipt + tells the UI it's safe
    to clear the form."""

    received: bool = True


@router.post(
    "/inquiry",
    response_model=SalesInquiryResponse,
    status_code=201,
)
@limiter.limit("5/hour")
async def submit_sales_inquiry(
    request: Request,
    data: SalesInquiry,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Capture a new institutional inquiry.

    Authenticated callers get their ``user_id`` stamped on the lead so
    support can immediately see "this is an existing customer asking
    about a different tier". Anonymous callers (the typical case) get
    ``user_id=NULL`` — a cold lead.
    """
    lead = SalesLead(
        id=str(uuid.uuid4()),
        email=str(data.email),
        name=data.name.strip(),
        institution=data.institution.strip() if data.institution else None,
        team_size=data.team_size.strip() if data.team_size else None,
        message=data.message.strip() if data.message else None,
        user_id=current_user.id if current_user is not None else None,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)

    # Best-effort notify. Goes to a generic ops inbox; in dev the email
    # stub just logs. Don't fail the request if Resend chokes.
    try:
        notification_to = settings.EMAIL_FROM.split("<")[-1].rstrip(">").strip()
        # Crude — strips "Name <addr>" wrapper. In Phase E we'd add a
        # dedicated SALES_NOTIFICATION_EMAIL but for now reuse the
        # configured FROM address as a placeholder so dev works.
        subject = f"[Sales] New inquiry from {data.name}"
        body_lines = [
            f"From: {data.name} <{data.email}>",
            f"Institution: {data.institution or '(not provided)'}",
            f"Team size: {data.team_size or '(not provided)'}",
            f"Logged in as: {current_user.email if current_user else '(anonymous)'}",
            "",
            "Message:",
            (data.message or "(none)"),
        ]
        text = "\n".join(body_lines)
        html = (
            "<p>"
            + "<br>".join(line if line else "" for line in body_lines)
            + "</p>"
        )
        await send_email(
            to=notification_to,
            subject=subject,
            html=html,
            text=text,
        )
    except Exception:
        logger.exception("sales inquiry notification email failed for lead=%s", lead.id)

    return SalesInquiryResponse()
