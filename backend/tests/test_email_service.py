"""Tests for the Resend-backed email service.

Templates are pure functions — straight assertions. The sender mocks the
Resend HTTP endpoint via ``respx`` to mirror the rest of the suite.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.services.email import (
    is_configured,
    render_password_reset,
    render_scheduled_report_ready,
    render_verify_email,
    send_email,
)
from app.services.email.sender import _redact


# ─── Template tests ────────────────────────────────────────────────────────


def test_password_reset_template_escapes_html_in_name():
    subject, html, text = render_password_reset(
        name="<script>alert(1)</script>",
        reset_url="https://example.com/reset/abc",
        ttl_hours=1,
    )
    assert subject == "Reset your ArtiProof password"
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "https://example.com/reset/abc" in html
    assert "https://example.com/reset/abc" in text


def test_verify_email_template_includes_ttl_and_name():
    _, html, _ = render_verify_email(
        name="Researcher",
        verify_url="https://example.com/verify/x",
        ttl_hours=24,
    )
    assert "Researcher" in html
    assert "expires in 24 hours" in html


def test_scheduled_report_template_uses_window_label():
    subject, html, text = render_scheduled_report_ready(
        name="Dr. Smith",
        report_title="Weekly Activity Summary",
        report_url="https://example.com/reports/abc",
        window_label="weekly",
    )
    assert "weekly" in subject
    assert "Dr. Smith" in html
    assert "https://example.com/reports/abc" in text


def test_scheduled_report_subject_is_text_not_html_escaped():
    # Mail clients render the subject as plain text; HTML-escaping it
    # would turn "Q1 & Q2" into "Q1 &amp; Q2" in Gmail. Body still
    # escapes (the report title appears inside <strong>...</strong>).
    subject, html, _ = render_scheduled_report_ready(
        name="Dr. Smith",
        report_title="Smith & Jones Report",
        report_url="https://example.com/reports/xyz",
        window_label="Q1 & Q2",
    )
    assert "Q1 & Q2" in subject
    assert "&amp;" not in subject
    # Body still escapes the title.
    assert "Smith &amp; Jones Report" in html


def test_render_handles_empty_name_gracefully():
    _, html, text = render_password_reset(
        name="", reset_url="https://x.example/r", ttl_hours=1
    )
    assert "Hi there" in html
    assert "Hi there" in text


# ─── Redaction helper ──────────────────────────────────────────────────────


def test_redact_keeps_domain_and_hashes_local_part():
    redacted = _redact("alice@example.com")
    assert redacted.endswith("@example.com")
    # 8-char prefix means we don't echo the local part anywhere.
    local, _, _ = redacted.partition("@")
    assert len(local) == 8
    assert "alice" not in redacted


def test_redact_is_stable_across_calls():
    # Same address must produce the same digest so log searches work.
    assert _redact("a@b.com") == _redact("a@b.com")


def test_redact_distinguishes_addresses():
    assert _redact("alice@x.com") != _redact("bob@x.com")


def test_redact_handles_missing_at_sign():
    # Garbage in shouldn't crash the logger; just yield "?"-domain.
    redacted = _redact("not-an-email")
    assert redacted.endswith("@?")


# ─── Sender tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_email_falls_back_to_logging_without_key(monkeypatch, caplog):
    """Without RESEND_API_KEY the sender stubs out: logs and returns True.

    The INFO log line must NOT contain the raw address — only the
    redacted `<sha8>@<domain>` form. Full address is allowed at DEBUG.
    """
    monkeypatch.setattr("app.config.settings.RESEND_API_KEY", "")
    assert is_configured() is False
    with caplog.at_level("INFO"):
        ok = await send_email(
            to="alice@example.com",
            subject="Hi",
            html="<p>Hi</p>",
            text="Hi",
        )
    assert ok is True
    info_lines = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
    assert any("[email-stub]" in line for line in info_lines)
    # PII contract: full local-part of the address must never appear
    # at INFO. The domain (used for routing diagnosis) is fine.
    assert not any("alice@example.com" in line for line in info_lines)
    assert any("@example.com" in line for line in info_lines)


@pytest.mark.asyncio
@respx.mock
async def test_send_email_posts_to_resend_when_configured(monkeypatch):
    """With RESEND_API_KEY the sender POSTs the rendered payload."""
    monkeypatch.setattr("app.config.settings.RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(
        "app.config.settings.EMAIL_FROM", "ArtiProof <noreply@example.invalid>"
    )

    route = respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(200, json={"id": "msg_123"})
    )

    ok = await send_email(
        to="user@example.com",
        subject="Hello",
        html="<p>Hello</p>",
        text="Hello",
    )

    assert ok is True
    assert route.called
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer re_test_key"
    import json as _json

    body = _json.loads(request.content)
    assert body["to"] == ["user@example.com"]
    assert body["subject"] == "Hello"
    assert body["html"] == "<p>Hello</p>"
    assert body["text"] == "Hello"
    assert body["from"] == "ArtiProof <noreply@example.invalid>"


@pytest.mark.asyncio
@respx.mock
async def test_send_email_returns_false_on_4xx(monkeypatch, caplog):
    """A 4xx from Resend is logged but doesn't raise."""
    monkeypatch.setattr("app.config.settings.RESEND_API_KEY", "re_test_key")
    respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(422, json={"error": "from address not verified"})
    )

    with caplog.at_level("ERROR"):
        ok = await send_email(
            to="user@example.com",
            subject="Hi",
            html="<p>Hi</p>",
        )

    assert ok is False
    assert any("Resend rejected" in r.message for r in caplog.records)


@pytest.mark.asyncio
@respx.mock
async def test_send_email_omits_text_when_not_provided(monkeypatch):
    """text is optional — payload should omit the key entirely if None."""
    monkeypatch.setattr("app.config.settings.RESEND_API_KEY", "re_test_key")
    route = respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(200, json={"id": "x"})
    )

    await send_email(to="x@y.example", subject="s", html="<p>h</p>")

    import json as _json

    body = _json.loads(route.calls.last.request.content)
    assert "text" not in body
