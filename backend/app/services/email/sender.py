"""Email sender — Resend API client with a dev fallback.

Sender precedence:
  1. RESEND_API_KEY set → POST to Resend's REST API.
  2. Otherwise → log the email at INFO and return success.

The fallback lets `forgot-password` and `verify-email` keep working
locally without a Resend account. Production is expected to set the key;
`is_configured()` exposes that fact so `main.py` can warn at startup.

Resend was chosen because it has a $0 free tier (3K emails/month),
DKIM/SPF baked in, a clean REST API (no SDK dependency), and no per-call
overhead beyond a single httpx POST. Swapping to Postmark/Sendgrid later
is a single-file change.
"""

from __future__ import annotations

import hashlib
import logging

import httpx

from app.config import settings
from app.utils.retry import HTTP_RETRY_EXCEPTIONS, with_retry

logger = logging.getLogger(__name__)


RESEND_ENDPOINT = "https://api.resend.com/emails"


def _redact(address: str) -> str:
    """Return a log-safe identifier for an email address.

    INFO-level logs ship to aggregators (Sentry, CloudWatch) where they
    can be indexed. A full email is PII; the domain + an 8-char SHA-256
    prefix lets ops correlate sends without leaking the address itself.
    The full address still appears at DEBUG for in-process diagnosis.
    """
    domain = address.split("@", 1)[1] if "@" in address else "?"
    digest = hashlib.sha256(address.encode("utf-8")).hexdigest()[:8]
    return f"{digest}@{domain}"


def is_configured() -> bool:
    """True when a real provider is wired. Used by startup checks."""
    return bool(settings.RESEND_API_KEY)


@with_retry(max_retries=2, exceptions=HTTP_RETRY_EXCEPTIONS)
async def _post_resend(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            RESEND_ENDPOINT,
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def send_email(
    *,
    to: str,
    subject: str,
    html: str,
    text: str | None = None,
    from_addr: str | None = None,
) -> bool:
    """Send a transactional email. Returns True on success.

    Always returns True in the unconfigured-dev path so call sites don't
    have to branch — they should treat the boolean as "delivery was
    attempted", not "the recipient definitely got it".
    """
    sender = from_addr or settings.EMAIL_FROM
    redacted = _redact(to)
    if not is_configured():
        # Dev fallback: surface the message so a developer running the
        # flow locally can copy the link from logs. Includes the full
        # address + rendered HTML at DEBUG so local debugging still works.
        logger.info("[email-stub] to=%s subject=%s (Resend not configured)", redacted, subject)
        logger.debug("[email-stub] full_to=%s html=%s", to, html)
        return True

    payload: dict = {
        "from": sender,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    try:
        await _post_resend(payload)
        logger.info("Email sent to=%s subject=%s", redacted, subject)
        logger.debug("Email sent full_to=%s", to)
        return True
    except httpx.HTTPStatusError as e:
        # 4xx — bad config or address. Log full body so the operator can
        # tell whether DNS verification failed vs the user typed a bad
        # address. Don't raise — caller already returned 200 to the user.
        # We do log the full address here (ERROR level) because resolving
        # a bounce without it is impractical; this stays out of routine
        # INFO traffic.
        logger.error(
            "Resend rejected email to=%s status=%d body=%s",
            to,
            e.response.status_code,
            e.response.text[:500],
        )
        return False
    except Exception:
        logger.exception("Email send failed to=%s subject=%s", redacted, subject)
        return False
