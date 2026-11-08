"""PDF generator — converts HTML reports to PDF.

Primary path: WeasyPrint (faithful CSS rendering — the report HTML is
designed for it). On Windows hosts where WeasyPrint's native GTK / Cairo
/ Pango dependencies aren't installed, WeasyPrint's import fails and we
fall through to a PyMuPDF-based plain-text renderer.

The fallback produces a basic-but-readable PDF (title heading, sectioned
paragraphs, no styling). It's intentionally ugly because it should never
ship to production — operators install GTK and the styled WeasyPrint
path takes over.

Public API:
  - html_to_pdf(html) -> (bytes, renderer_name) — returns the bytes
    AND a renderer label ("weasyprint" | "pymupdf-fallback") so the
    route can set X-Report-Renderer for the frontend to surface a
    caveat toast.
  - save_pdf(bytes) -> filepath — unchanged.
  - WEASYPRINT_AVAILABLE — module-level bool, evaluated once at import.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from html import unescape
from typing import Tuple

logger = logging.getLogger(__name__)

PDF_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "reports")


# ─── WeasyPrint availability probe ─────────────────────────────────────────
# Imported once at module load so we don't pay the (failing-on-Windows)
# import cost on every request. A failed probe is logged once at WARNING
# level — operators see "PDF styled-renderer disabled, falling back to
# plain text" exactly once in the startup logs and know to install GTK.
WEASYPRINT_AVAILABLE: bool = False
_WEASYPRINT_HTML = None
try:  # pragma: no cover - environment-dependent
    from weasyprint import HTML as _WEASYPRINT_HTML_CLASS  # type: ignore

    WEASYPRINT_AVAILABLE = True
    _WEASYPRINT_HTML = _WEASYPRINT_HTML_CLASS
except Exception as e:  # pragma: no cover - environment-dependent
    logger.warning(
        "WeasyPrint unavailable (%s) — styled PDF rendering disabled; "
        "report downloads will use the plain-text fallback. Install GTK + "
        "Pango on Windows or the equivalent system libs on Linux to enable "
        "styled rendering.",
        type(e).__name__,
    )


def html_to_pdf(html: str) -> Tuple[bytes, str]:
    """Convert HTML string to PDF bytes + a renderer label.

    Returns a (pdf_bytes, renderer) tuple where `renderer` is one of:
      - "weasyprint" — full CSS rendering, what the design expects
      - "pymupdf-fallback" — basic text-only fallback (Windows / no GTK)
    The route layer reads `renderer` and stamps an `X-Report-Renderer`
    response header so the frontend can show a caveat toast.
    """
    if WEASYPRINT_AVAILABLE and _WEASYPRINT_HTML is not None:
        try:
            return _WEASYPRINT_HTML(string=html).write_pdf(), "weasyprint"
        except Exception:
            logger.exception(
                "WeasyPrint PDF generation failed at runtime — falling "
                "back to plain-text renderer for this request"
            )
            return _html_to_simple_pdf(html), "pymupdf-fallback"
    return _html_to_simple_pdf(html), "pymupdf-fallback"


def _html_to_simple_pdf(html: str) -> bytes:
    """Fallback PDF renderer used when WeasyPrint / native libs are absent.

    Renders a basic, readable PDF: title at top, sectioned paragraphs
    underneath, page breaks on overflow. Not pretty — that's intentional
    so the operator knows the styled path failed and installs GTK.
    """
    try:
        import fitz
    except Exception:
        logger.exception("PyMuPDF fallback unavailable")
        raise

    title = _extract_title(html) or "ArtiProof Report"
    body_text = _html_to_plain_text(html)

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 points

    margin = 48
    y = margin
    line_height = 14
    max_chars = 92

    # Title — 18pt bold so the operator/customer at least sees what the
    # report is about even in fallback mode.
    page.insert_text(
        (margin, y),
        title[:120],
        fontsize=18,
        fontname="helv",
        color=(0.30, 0.10, 0.10),  # wine-ish
    )
    y += 28

    # Caveat line — make the fallback transparent.
    page.insert_text(
        (margin, y),
        "(Styled rendering unavailable — text-only fallback)",
        fontsize=8,
        fontname="helv",
        color=(0.5, 0.5, 0.5),
    )
    y += 18

    # Body
    for paragraph in body_text.splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            y += line_height
            continue

        words = paragraph.split()
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if len(candidate) > max_chars:
                y = _write_pdf_line(doc, page, line, margin, y, line_height)
                if y > 790:
                    page = doc.new_page(width=595, height=842)
                    y = margin
                line = word
            else:
                line = candidate

        if line:
            y = _write_pdf_line(doc, page, line, margin, y, line_height)
            if y > 790:
                page = doc.new_page(width=595, height=842)
                y = margin

        y += 4

    return doc.tobytes()


def _write_pdf_line(doc, page, line: str, x: int, y: int, line_height: int) -> int:
    page.insert_text((x, y), line, fontsize=10, fontname="helv", color=(0.05, 0.09, 0.16))
    return y + line_height


def _extract_title(html: str) -> str | None:
    """Pull the first <h1> or <title> text out of the HTML so the
    fallback PDF can lead with something meaningful instead of opening
    on a paragraph."""
    for pattern in (r"<h1[^>]*>(.*?)</h1>", r"<title[^>]*>(.*?)</title>"):
        m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if m:
            text = re.sub(r"<[^>]+>", " ", m.group(1))
            text = unescape(text).strip()
            if text:
                return text
    return None


def _html_to_plain_text(html: str) -> str:
    # Strip the title before plain-text conversion so it doesn't appear
    # twice in the rendered PDF (header + first paragraph).
    html_no_h1 = re.sub(r"<h1[^>]*>.*?</h1>", "", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", html_no_h1)
    text = re.sub(r"(?i)</\s*(p|div|h[1-6]|li|tr)\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def save_pdf(pdf_bytes: bytes) -> str:
    """Save PDF bytes to disk and return the file path."""
    os.makedirs(PDF_DIR, exist_ok=True)
    filename = f"report_{uuid.uuid4().hex[:12]}.pdf"
    filepath = os.path.join(PDF_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(pdf_bytes)
    return filepath
