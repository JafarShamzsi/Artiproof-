"""
Shared utility functions.
"""

import hashlib
from datetime import datetime, timezone


def generate_scan_id(content: str) -> str:
    """Generate a deterministic scan ID from content."""
    timestamp = datetime.now(timezone.utc).isoformat()
    raw = f"{content[:256]}:{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)
