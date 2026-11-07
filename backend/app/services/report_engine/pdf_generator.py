"""
PDF generator — converts HTML reports to PDF using WeasyPrint.
"""

import logging
import os
import re
import uuid
from html import unescape

logger = logging.getLogger(__name__)

PDF_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "reports")


def html_to_pdf(html: str) -> bytes:
    """Convert HTML string to PDF bytes."""
    try:
        from weasyprint import HTML
        return HTML(string=html).write_pdf()
    except ImportError:
        logger.warning("WeasyPrint not installed, using simple PDF fallback")
        return _html_to_simple_pdf(html)
    except Exception:
        logger.exception("WeasyPrint PDF generation failed, using simple PDF fallback")
        return _html_to_simple_pdf(html)


def _html_to_simple_pdf(html: str) -> bytes:
    """Fallback PDF renderer used when WeasyPrint/native Cairo libs are unavailable."""
    try:
        import fitz
    except Exception:
        logger.exception("PyMuPDF fallback unavailable")
        raise

    text = _html_to_plain_text(html)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 points

    margin = 48
    y = margin
    line_height = 14
    max_chars = 92

    for paragraph in text.splitlines():
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


def _html_to_plain_text(html: str) -> str:
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", html)
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
