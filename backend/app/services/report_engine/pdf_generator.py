"""PDF generator — converts HTML reports to PDF.

Two *structured* renderers tried in order, plus a plain-text safety net:

  1. WeasyPrint ("weasyprint") — faithful CSS rendering incl. flexbox and
     border-radius; the report HTML is designed for it. Needs native
     GTK / Cairo / Pango libs, so it can be unavailable on bare Windows
     hosts or minimal containers.
  2. PyMuPDF Story ("pymupdf-story") — used when WeasyPrint is absent or
     errors at runtime. Renders the SAME HTML (and its ``<style>`` block)
     into a structured, styled PDF with NO native dependencies, so it
     works identically in local dev, Docker, and local service. Degrades
     gracefully vs WeasyPrint (square score badge, no flexbox) but is
     never a raw text/CSS dump.
  3. Plain-text ("pymupdf-text") — last resort, reached only if the Story
     renderer itself raises. Title + sectioned paragraphs, no styling.

Public API:
  - html_to_pdf(html) -> (bytes, renderer_name) — the bytes AND the
    renderer label above, so the route can stamp X-Report-Renderer (ops
    can see when WeasyPrint is down; the frontend only warns for the
    bare "pymupdf-text" last resort).
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
      - "weasyprint"    — full CSS rendering, what the design expects
      - "pymupdf-story" — structured PyMuPDF render (no native libs).
                          Applies the report's CSS (headings, colored
                          cards, tables) — degrades gracefully vs
                          WeasyPrint (square score badge, stacked stat
                          cards) but is NOT a bare text dump.
      - "pymupdf-text"  — last-resort plain-text render, only if the
                          Story renderer itself errored.
    The route layer reads `renderer` and stamps an `X-Report-Renderer`
    response header (ops can see when WeasyPrint is down).
    """
    if WEASYPRINT_AVAILABLE and _WEASYPRINT_HTML is not None:
        try:
            return _WEASYPRINT_HTML(string=html).write_pdf(), "weasyprint"
        except Exception:
            logger.exception(
                "WeasyPrint PDF generation failed at runtime — falling "
                "back to the PyMuPDF Story renderer for this request"
            )
    # No WeasyPrint (or it errored): render structured HTML with PyMuPDF's
    # Story engine, which needs no native system libraries and still
    # honours the report's CSS. Only if that ALSO fails do we drop to the
    # plain-text last resort.
    try:
        return _html_to_pdf_story(html), "pymupdf-story"
    except Exception:
        logger.exception(
            "PyMuPDF Story renderer failed — using plain-text last resort"
        )
        return _html_to_simple_pdf(html), "pymupdf-text"


def _html_to_pdf_story(html: str) -> bytes:
    """Structured fallback renderer using PyMuPDF's Story API.

    Unlike the plain-text path, Story parses the HTML *and its ``<style>``
    block* and lays out a real document: headings, paragraphs, colored
    claim cards, and tables all survive. It does not support every CSS
    feature WeasyPrint does (no flexbox, no ``border-radius``), so the
    score badge renders square and the stat cards stack — acceptable
    degradation, and crucially never a raw-CSS dump.

    Needs no native system libraries (pure MuPDF), so it works identically
    in local dev, Docker, and local service.
    """
    import io

    import fitz

    buf = io.BytesIO()
    writer = fitz.DocumentWriter(buf)
    story = fitz.Story(html=html)
    media = fitz.paper_rect("a4")
    # ~12.7mm content margins; the @page margin in the HTML is ignored by
    # Story, so we inset the draw area ourselves.
    area = media + (36, 36, -36, -36)

    more = 1
    pages = 0
    while more:
        dev = writer.begin_page(media)
        more, _ = story.place(area)
        story.draw(dev)
        writer.end_page()
        pages += 1
        if pages >= 200:  # defensive cap against a pathological layout loop
            logger.warning("Story renderer hit 200-page cap; truncating report")
            break
    writer.close()
    return buf.getvalue()


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
    # Drop <style>/<script> blocks (tags AND their contents) first — the
    # generic tag-stripper below only removes the tags, which would leave
    # the raw CSS/JS body as visible text (the "HTML dump" bug).
    html = re.sub(
        r"(?is)<\s*(style|script)\b[^>]*>.*?<\s*/\s*\1\s*>", "", html
    )
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
