"""Email delivery — Resend by default, no-op when RESEND_API_KEY is absent.

The public API is `send_email()` — providers below are implementation
detail. Templates live alongside in `templates.py` so call sites stay
small (one function call per kind).

The provider selection is intentionally simple: if RESEND_API_KEY is set
we use Resend; otherwise we fall back to logging. This avoids the trap of
quietly failing in production — `is_configured()` lets the operator log
a startup warning when prod is unconfigured.
"""

from app.services.email.sender import is_configured, send_email
from app.services.email.templates import (
    render_org_invite,
    render_password_reset,
    render_scheduled_report_ready,
    render_verify_email,
)

__all__ = [
    "is_configured",
    "render_org_invite",
    "render_password_reset",
    "render_scheduled_report_ready",
    "render_verify_email",
    "send_email",
]
