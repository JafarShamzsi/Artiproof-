"""
PDF generator — converts HTML reports to PDF using WeasyPrint.
"""

import logging
import os
import uuid

logger = logging.getLogger(__name__)

PDF_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "reports")


def html_to_pdf(html: str) -> bytes:
    """Convert HTML string to PDF bytes."""
    try:
        from weasyprint import HTML
        return HTML(string=html).write_pdf()
    except ImportError:
        logger.warning("WeasyPrint not installed, returning empty PDF")
        return b"%PDF-1.4 (WeasyPrint not available)"
    except Exception:
        logger.exception("PDF generation failed")
        raise


def save_pdf(pdf_bytes: bytes) -> str:
    """Save PDF bytes to disk and return the file path."""
    os.makedirs(PDF_DIR, exist_ok=True)
    filename = f"report_{uuid.uuid4().hex[:12]}.pdf"
    filepath = os.path.join(PDF_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(pdf_bytes)
    return filepath
