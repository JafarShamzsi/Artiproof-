"""
PDF annotator — creates a highlighted copy of the original PDF with color-coded annotations.

Colors:
- Red:    FALSE / MISLEADING claims
- Orange: PARTIALLY_TRUE / UNVERIFIED claims
- Green:  TRUE claims (subtle)
- Purple: AI-detected paragraphs (opacity scales with probability)
- Yellow: Citation issues
"""

import logging
from typing import Optional

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


# RGB colors (0-1 range for PyMuPDF)
COLORS = {
    "false": (0.93, 0.27, 0.27),       # Red
    "misleading": (0.93, 0.27, 0.27),   # Red
    "partially_true": (0.96, 0.62, 0.04),  # Orange
    "unverified": (0.96, 0.62, 0.04),   # Orange
    "true": (0.06, 0.73, 0.51),         # Green
    "ai_content": (0.66, 0.33, 0.97),   # Purple
    "citation_issue": (0.96, 0.83, 0.18),  # Yellow
}


def create_annotated_pdf(
    original_pdf_path: str,
    position_map: dict,
    claims: list[dict],
    ai_detections: list[dict],
    citations: list[dict],
) -> Optional[str]:
    """
    Create a copy of the PDF with highlight annotations overlaid.

    Args:
        original_pdf_path: Path to the original uploaded PDF
        position_map: Output from map_all_findings_to_positions()
        claims: List of claim dicts with id, verdict, confidence
        ai_detections: List of AI detection dicts with id, ai_probability
        citations: List of citation dicts with id, is_retracted, is_accessible

    Returns:
        Path to the annotated PDF, or None on failure.
    """
    try:
        if original_pdf_path.startswith("artifact://"):
            from app.services.artifact_storage import read_pdf

            doc = fitz.open(stream=read_pdf(original_pdf_path), filetype="pdf")
        else:
            doc = fitz.open(original_pdf_path)
    except Exception:
        logger.exception("Failed to open PDF for annotation: %s", original_pdf_path)
        return None

    try:
        # Annotate claims
        claim_map = position_map.get("claims", {})
        for claim in claims:
            claim_id = claim.get("id", "")
            verdict = claim.get("verdict", "unverified")
            confidence = claim.get("confidence", 0.5)

            if claim_id not in claim_map:
                continue

            color = COLORS.get(verdict, COLORS["unverified"])
            opacity = 0.25 + (confidence * 0.2)  # 0.25 to 0.45

            for hl in claim_map[claim_id].get("highlights", []):
                _add_highlight(doc, hl["page"], hl["bbox"], color, opacity)

        # Annotate AI detections
        ai_map = position_map.get("ai_detections", {})
        for detection in ai_detections:
            det_id = detection.get("id", "")
            ai_prob = detection.get("ai_probability", 0.5)

            if det_id not in ai_map:
                continue

            # Only highlight if probability > 0.3
            if ai_prob < 0.3:
                continue

            color = COLORS["ai_content"]
            opacity = 0.15 + (ai_prob * 0.3)  # 0.15 to 0.45

            for hl in ai_map[det_id].get("highlights", []):
                _add_highlight(doc, hl["page"], hl["bbox"], color, opacity)

        # Annotate citation issues
        cit_map = position_map.get("citations", {})
        for citation in citations:
            cit_id = citation.get("id", "")
            has_issue = citation.get("is_retracted") or not citation.get("is_accessible", True)

            if not has_issue or cit_id not in cit_map:
                continue

            color = COLORS["citation_issue"]
            opacity = 0.35

            for hl in cit_map[cit_id].get("highlights", []):
                _add_highlight(doc, hl["page"], hl["bbox"], color, opacity)

        # Save annotated copy
        from app.services.artifact_storage import put_pdf

        output_path = put_pdf(doc.tobytes(), "annotated")
        doc.close()

        return output_path

    except Exception:
        logger.exception("PDF annotation failed")
        doc.close()
        return None


def _add_highlight(
    doc: fitz.Document,
    page_number: int,
    bbox: list[float],
    color: tuple[float, float, float],
    opacity: float,
) -> None:
    """Add a highlight annotation to a specific page at the given bbox."""
    if page_number >= len(doc):
        return

    page = doc[page_number]
    rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])

    try:
        annot = page.add_highlight_annot(rect)
        annot.set_colors(stroke=color)
        annot.set_opacity(min(1.0, max(0.1, opacity)))
        annot.update()
    except Exception:
        # If highlight_annot fails (e.g., bad rect), draw a filled rect instead
        try:
            shape = page.new_shape()
            shape.draw_rect(rect)
            shape.finish(color=None, fill=color, fill_opacity=opacity)
            shape.commit()
        except Exception:
            logger.debug("Failed to annotate rect on page %d", page_number)
