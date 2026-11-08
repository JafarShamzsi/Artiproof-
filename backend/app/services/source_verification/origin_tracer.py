"""Attribution for false/misleading claims — grounded, not speculated.

The previous implementation asked an LLM to "trace where the misinformation
originated and how it spread." That's ungrounded: the model has no way to know
a novel claim's origin, so it fabricates a plausible platform, date, and
spread path and returns them with a confidence score — exactly the kind of
invented "fact" this product exists to catch.

This version makes no such claim. It attributes a false/misleading claim to
the **real, independent fact-check** already retrieved for it (Google Fact
Check Tools): who flagged it, with what rating, and when. If no independent
review exists, it returns ``None`` — we don't manufacture an origin.
"""

import logging

logger = logging.getLogger(__name__)


def trace_origin(verdict: str, factcheck_review: dict | None) -> dict | None:
    """Build a grounded attribution record for a flagged claim.

    Args:
        verdict: the claim's verdict; only ``"false"``/``"misleading"`` are
            attributed.
        factcheck_review: the earliest existing fact-check for the claim
            (``publisher``/``url``/``rating``/``review_date``), or ``None``.

    Returns a dict with ``flagged_by`` / ``review_date`` / ``review_url`` /
    ``rating`` / ``source``, or ``None`` when there is no real review to cite.
    """
    if verdict not in ("false", "misleading"):
        return None
    if not factcheck_review or not factcheck_review.get("publisher"):
        return None
    return {
        "flagged_by": factcheck_review.get("publisher"),
        "review_date": factcheck_review.get("review_date"),
        "review_url": factcheck_review.get("url"),
        "rating": factcheck_review.get("rating"),
        "source": "google_factcheck",
    }
