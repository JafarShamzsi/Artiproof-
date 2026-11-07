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


# ─── Plan tiers ───────────────────────────────────────────────────────────
# Per-month quotas. None = unlimited. Used by /api/dashboard/usage and as
# soft hints in the UI; hard enforcement is opt-in per route via
# enforce_quota dependency.
TIER_LIMITS: dict[str, dict[str, int | None]] = {
    "free": {
        "source_checks_per_month": 10,
        "researcher_analyses_per_month": 5,
        "reports_per_month": 5,
    },
    "pro": {
        "source_checks_per_month": 100,
        "researcher_analyses_per_month": 50,
        "reports_per_month": 50,
    },
    "team": {
        "source_checks_per_month": None,
        "researcher_analyses_per_month": None,
        "reports_per_month": None,
    },
}

# Default notification preferences for newly created users. Keep keys stable —
# the User.notification_preferences JSON merges with these on read so we can
# add new keys without backfilling rows.
DEFAULT_NOTIFICATION_PREFERENCES: dict[str, bool] = {
    "email_on_completion": True,
    "email_on_low_credibility": True,
    "email_weekly_digest": False,
    "email_product_updates": False,
}

# Supported UI locales. Frontend renders the selector against this list and
# stores the user's choice. Translation infrastructure (next-intl) is a
# separate phase; for now we just persist the preference.
SUPPORTED_LOCALES = ("en", "az", "ru")
