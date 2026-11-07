"""Cross-cutting numeric constants.

Per-module weights and thresholds (e.g. WEIGHT_FALSE_CLAIM in
source_verification.orchestrator, FIELD_THRESHOLDS in ring_detector)
live next to their use-sites — they're tightly coupled to the formula
they belong to, and moving them here would just create false coupling.

What lives here is the genuinely shared stuff: file-size caps, score
bounds, hard limits that more than one module enforces.
"""

from __future__ import annotations

# Score bounds — final credibility / integrity scores clamped to this range.
CREDIBILITY_SCORE_MIN = 0.0
CREDIBILITY_SCORE_MAX = 100.0

# File upload limits (PDF source checks).
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MIN_FILE_SIZE_BYTES = 100  # below this it can't possibly be a real PDF
