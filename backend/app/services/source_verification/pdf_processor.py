"""
PDF processor — extracts text from PDF files with position data using PyMuPDF.

Provides:
- Full text extraction with page/block/bbox coordinates
- Mapping from text character offsets back to PDF positions
"""

import logging
from typing import Optional

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def extract_text_with_positions(pdf_path: str) -> dict:
    """
    Extract all text from a PDF with position data for every text block.

    Returns:
        {
            "full_text": "entire document text...",
            "pages": [
                {
                    "page_number": 0,
                    "width": 612.0,
                    "height": 792.0,
                    "blocks": [
                        {
                            "text": "paragraph text...",
                            "bbox": [x0, y0, x1, y1],
                            "block_index": 0,
                            "char_start": 0,     # offset in full_text
                            "char_end": 150,
                        }
                    ]
                }
            ]
        }
    """
    doc = fitz.open(pdf_path)
    pages = []
    full_text_parts = []
    char_offset = 0

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        blocks_data = []

        # Get text blocks — each block is (x0, y0, x1, y1, "text", block_no, block_type)
        blocks = page.get_text("blocks")

        for block_no, block in enumerate(blocks):
            # block_type 0 = text, 1 = image
            if block[6] != 0:
                continue

            text = block[4].strip()
            if not text or len(text) < 5:
                continue

            bbox = [round(block[0], 2), round(block[1], 2),
                    round(block[2], 2), round(block[3], 2)]

            char_start = char_offset
            char_end = char_offset + len(text)

            blocks_data.append({
                "text": text,
                "bbox": bbox,
                "block_index": block_no,
                "char_start": char_start,
                "char_end": char_end,
            })

            full_text_parts.append(text)
            char_offset = char_end + 1  # +1 for the newline separator

        pages.append({
            "page_number": page_idx,
            "width": round(page.rect.width, 2),
            "height": round(page.rect.height, 2),
            "blocks": blocks_data,
        })

    doc.close()

    return {
        "full_text": "\n".join(full_text_parts),
        "pages": pages,
    }


def map_text_to_pdf_position(
    extracted_data: dict,
    text_start: int,
    text_end: int,
) -> Optional[dict]:
    """
    Given character offsets in the full_text, return the PDF page(s) and bbox(es).

    Returns:
        {
            "page": 3,
            "highlights": [
                {"bbox": [x0, y0, x1, y1], "page": 3}
            ]
        }
    or None if position cannot be mapped.
    """
    highlights = []

    for page_data in extracted_data.get("pages", []):
        for block in page_data.get("blocks", []):
            block_start = block["char_start"]
            block_end = block["char_end"]

            # Check if this block overlaps with the requested range
            if block_end <= text_start or block_start >= text_end:
                continue

            highlights.append({
                "bbox": block["bbox"],
                "page": page_data["page_number"],
            })

    if not highlights:
        return None

    return {
        "page": highlights[0]["page"],
        "highlights": highlights,
    }


def map_paragraph_to_pdf_position(
    extracted_data: dict,
    paragraph_text: str,
) -> Optional[dict]:
    """
    Find a paragraph in the extracted data by fuzzy text matching.
    Returns position data or None.
    """
    # Normalize for matching
    search = paragraph_text[:100].strip().lower()

    for page_data in extracted_data.get("pages", []):
        for block in page_data.get("blocks", []):
            block_text = block["text"][:100].strip().lower()
            # Check if the paragraph starts similarly
            if search[:50] in block_text or block_text[:50] in search:
                return {
                    "page": page_data["page_number"],
                    "highlights": [{"bbox": block["bbox"], "page": page_data["page_number"]}],
                }

    return None


def map_all_findings_to_positions(
    extracted_data: dict,
    claims: list[dict],
    ai_detections: list[dict],
    citations: list[dict],
) -> dict:
    """
    Build a complete position map for all findings.

    Returns:
        {
            "claims": {claim_id: {"page": N, "highlights": [...]}},
            "ai_detections": {detection_id: {"page": N, "highlights": [...]}},
            "citations": {citation_id: {"page": N, "highlights": [...]}},
        }
    """
    position_map = {"claims": {}, "ai_detections": {}, "citations": {}}

    for claim in claims:
        claim_id = claim.get("id", "")
        pos_data = claim.get("position_in_text")

        if pos_data and isinstance(pos_data, dict):
            start = pos_data.get("start", 0)
            end = pos_data.get("end", start + 100)
            mapped = map_text_to_pdf_position(extracted_data, start, end)
            if mapped:
                position_map["claims"][claim_id] = mapped
                continue

        # Fallback: match by claim text
        mapped = map_paragraph_to_pdf_position(extracted_data, claim.get("claim_text", ""))
        if mapped:
            position_map["claims"][claim_id] = mapped

    for detection in ai_detections:
        det_id = detection.get("id", "")
        mapped = map_paragraph_to_pdf_position(
            extracted_data, detection.get("paragraph_text", "")
        )
        if mapped:
            position_map["ai_detections"][det_id] = mapped

    for citation in citations:
        cit_id = citation.get("id", "")
        mapped = map_paragraph_to_pdf_position(
            extracted_data, citation.get("original_citation", "")
        )
        if mapped:
            position_map["citations"][cit_id] = mapped

    return position_map
