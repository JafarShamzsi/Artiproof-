"""HTML + plaintext templates for transactional email.

Each renderer returns a (subject, html, text) tuple so the call site
just unpacks once. Templates inline everything — no static assets, no
external CSS — so they render the same in every client.

Styling is intentionally minimal (system fonts, single accent color)
because Gmail/Outlook strip ~half of CSS anyway. The wine accent matches
the landing-page palette in PRODUCT.md.
"""

from __future__ import annotations

import html as _html

WINE = "#7A1C2F"
INK = "#1A1A1A"
MUTED = "#5E5E5E"

_BASE_STYLE = (
    "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
    f"color:{INK};line-height:1.5;max-width:560px;margin:0 auto;padding:32px"
)
_BUTTON_STYLE = (
    f"display:inline-block;background:{WINE};color:#FFFFFF;text-decoration:none;"
    "padding:12px 24px;border-radius:6px;font-weight:600;margin:16px 0"
)
_FOOTER_STYLE = f"color:{MUTED};font-size:13px;margin-top:32px;border-top:1px solid #E5E5E5;padding-top:16px"


def _wrap(body_html: str) -> str:
    return (
        f'<!DOCTYPE html><html><body style="{_BASE_STYLE}">'
        f'<div style="font-size:18px;font-weight:600;color:{WINE};margin-bottom:24px">'
        "ArtiProof"
        "</div>"
        f"{body_html}"
        f'<div style="{_FOOTER_STYLE}">'
        "ArtiProof · Research Integrity Platform<br>"
        "If you didn't expect this email, you can safely ignore it."
        "</div>"
        "</body></html>"
    )


def render_password_reset(*, name: str, reset_url: str, ttl_hours: int) -> tuple[str, str, str]:
    # `safe_*` are HTML-escaped for the body; subjects and text are raw
    # because mail clients render them as plain text. HTML-escaping the
    # subject turns "Q1 & Q2" into "Q1 &amp; Q2" in Gmail, which looks
    # broken.
    safe_name = _html.escape(name or "there")
    safe_url = _html.escape(reset_url, quote=True)
    subject = "Reset your ArtiProof password"
    html = _wrap(
        f"<p>Hi {safe_name},</p>"
        "<p>We received a request to reset the password on your ArtiProof account. "
        "Click the button below to choose a new one — the link expires in "
        f"{ttl_hours} hour{'s' if ttl_hours != 1 else ''}.</p>"
        f'<p><a href="{safe_url}" style="{_BUTTON_STYLE}">Reset password</a></p>'
        f'<p style="font-size:13px;color:{MUTED}">Or paste this URL into your browser:<br>'
        f'<a href="{safe_url}" style="color:{WINE};word-break:break-all">{safe_url}</a></p>'
        "<p>If you didn't request a reset, no action is needed — your password stays the same.</p>"
    )
    text = (
        f"Hi {name or 'there'},\n\n"
        "We received a request to reset the password on your ArtiProof account.\n"
        f"This link expires in {ttl_hours} hour{'s' if ttl_hours != 1 else ''}:\n\n"
        f"{reset_url}\n\n"
        "If you didn't request a reset, you can safely ignore this email.\n"
    )
    return subject, html, text


def render_verify_email(*, name: str, verify_url: str, ttl_hours: int) -> tuple[str, str, str]:
    safe_name = _html.escape(name or "there")
    safe_url = _html.escape(verify_url, quote=True)
    subject = "Verify your ArtiProof email"
    html = _wrap(
        f"<p>Hi {safe_name},</p>"
        "<p>Confirm your email address so we can send you analysis results, "
        "scheduled reports, and account alerts.</p>"
        f'<p><a href="{safe_url}" style="{_BUTTON_STYLE}">Verify email</a></p>'
        f'<p style="font-size:13px;color:{MUTED}">Or paste this URL into your browser:<br>'
        f'<a href="{safe_url}" style="color:{WINE};word-break:break-all">{safe_url}</a></p>'
        f"<p>This link expires in {ttl_hours} hours.</p>"
    )
    text = (
        f"Hi {name or 'there'},\n\n"
        "Confirm your email address so we can send you analysis results and scheduled reports.\n\n"
        f"{verify_url}\n\n"
        f"This link expires in {ttl_hours} hours.\n"
    )
    return subject, html, text


def render_org_invite(
    *, org_name: str, inviter_name: str, invite_url: str, ttl_days: int
) -> tuple[str, str, str]:
    """Render the "you've been invited to join an org" email.

    Two variants under one template:
    - Inviter has a name → "Alice has invited you to join Org X".
    - Anonymous inviter → "You've been invited to join Org X".
    """
    safe_org = _html.escape(org_name or "an ArtiProof team")
    safe_inviter = _html.escape(inviter_name) if inviter_name else None
    safe_url = _html.escape(invite_url, quote=True)
    # Subject + text body are raw — mail clients render as plain text.
    subject = f"Join {org_name or 'an ArtiProof team'} on ArtiProof"
    intro_html = (
        f"<p>{safe_inviter} has invited you to join <strong>{safe_org}</strong> on ArtiProof.</p>"
        if safe_inviter
        else f"<p>You've been invited to join <strong>{safe_org}</strong> on ArtiProof.</p>"
    )
    intro_text = (
        f"{inviter_name} has invited you to join {org_name or 'an ArtiProof team'} on ArtiProof."
        if inviter_name
        else f"You've been invited to join {org_name or 'an ArtiProof team'} on ArtiProof."
    )
    html = _wrap(
        intro_html
        + "<p>ArtiProof helps research teams audit citations, fact-check claims, "
        "detect AI-generated content, and score researcher integrity — and the "
        "team plan lets your whole org see each other's analyses.</p>"
        f'<p><a href="{safe_url}" style="{_BUTTON_STYLE}">Accept invitation</a></p>'
        f'<p style="font-size:13px;color:{MUTED}">Or paste this URL into your browser:<br>'
        f'<a href="{safe_url}" style="color:{WINE};word-break:break-all">{safe_url}</a></p>'
        f"<p>This invite expires in {ttl_days} day{'s' if ttl_days != 1 else ''}.</p>"
    )
    text = (
        f"{intro_text}\n\n"
        f"Accept your invitation:\n{invite_url}\n\n"
        f"This invite expires in {ttl_days} day{'s' if ttl_days != 1 else ''}.\n"
    )
    return subject, html, text


def render_scheduled_report_ready(
    *, name: str, report_title: str, report_url: str, window_label: str
) -> tuple[str, str, str]:
    # `safe_*` are HTML-escaped for the body; subjects + text body are
    # raw because mail clients render them as plain text. HTML-escaping
    # the subject turns "Q1 & Q2" into "Q1 &amp; Q2" in Gmail.
    safe_name = _html.escape(name or "there")
    safe_title = _html.escape(report_title)
    safe_url = _html.escape(report_url, quote=True)
    subject = f"Your {window_label} ArtiProof report is ready"
    html = _wrap(
        f"<p>Hi {safe_name},</p>"
        f"<p>Your scheduled <strong>{safe_title}</strong> report is ready to view.</p>"
        f'<p><a href="{safe_url}" style="{_BUTTON_STYLE}">Open report</a></p>'
        f'<p style="font-size:13px;color:{MUTED}">Or paste this URL into your browser:<br>'
        f'<a href="{safe_url}" style="color:{WINE};word-break:break-all">{safe_url}</a></p>'
        "<p>You can change the schedule or pause delivery from your Reports dashboard.</p>"
    )
    text = (
        f"Hi {name or 'there'},\n\n"
        f"Your scheduled '{report_title}' report is ready to view:\n\n"
        f"{report_url}\n\n"
        "You can change the schedule or pause delivery from your Reports dashboard.\n"
    )
    return subject, html, text
