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

# Per-user burst rate limits on expensive endpoints (source check, researcher
# analysis, report generation). These protect Gemini quota from a single
# attacker / runaway client; monthly volume is gated separately by TIER_LIMITS
# above. Anonymous fallback (unauthenticated) gets the strictest cap and uses
# the IP key bucket. See app.utils.rate_limit.tier_aware_limit_for_key.
TIER_RATE_LIMITS: dict[str, str] = {
    "free": "3/minute",
    "pro": "30/minute",
    "team": "120/minute",
}
# Used when no authenticated user can be resolved (token missing or invalid).
# Should be strictly tighter than `free` so an unauth caller can never burst
# more than a free tier user.
ANONYMOUS_RATE_LIMIT = "1/minute"

# Default notification preferences for newly created users. Keep keys stable —
# the User.notification_preferences JSON merges with these on read so we can
# add new keys without backfilling rows.
DEFAULT_NOTIFICATION_PREFERENCES: dict[str, bool] = {
    "email_on_completion": True,
    "email_on_low_credibility": True,
    "email_weekly_digest": False,
    "email_product_updates": False,
}

# Supported UI locales. English only for now — `az` and `ru` were aspirational
# and have been de-scoped until a real next-intl scaffold ships. The User.locale
# column stays so we don't have to backfill when i18n returns; the validator
# below rejects anything else so we don't promise what we don't deliver.
SUPPORTED_LOCALES = ("en",)


# ─── Analysis defaults ────────────────────────────────────────────────────
# Per-user defaults for the source-verification + researcher pipelines.
# Merged with User.analysis_preferences on read so adding a key never
# breaks existing rows. Settings page edits these values directly.
DEFAULT_ANALYSIS_PREFERENCES: dict[str, object] = {
    "check_citations": True,
    "trace_misinfo_origins": True,
    "ai_detection_model": "gemini-2.0-flash",
    "researcher_field_inference": True,
}

# ─── Full-document analysis (chunked) ──────────────────────────────────────
# Long inputs are split into overlapping character windows so claims are
# extracted from the whole document, not just the first window. Each window is
# one LLM call, so the per-analysis budget (max windows) is tier-gated to bound
# cost; beyond the budget the analysis stops and reports honest partial coverage.
ANALYSIS_WINDOW_CHARS = 12000
ANALYSIS_WINDOW_OVERLAP = 1000
ANALYSIS_WINDOW_CONCURRENCY = 4
ANALYSIS_MAX_CLAIMS_TOTAL = 40  # merged claim cap across all windows
ANALYSIS_WINDOW_BUDGET: dict[str, int] = {
    "free": 2,    # ~23k chars
    "pro": 8,     # ~89k chars
    "team": 20,   # ~221k chars
}
# AI-text detection is statistical (cheap), so it covers the whole document;
# this cap only guards against pathological inputs. The opt-in LLM cross-check
# stays bounded separately.
ANALYSIS_MAX_PARAGRAPHS = 200
ANALYSIS_LLM_CROSSCHECK_PARAGRAPHS = 20

# How long password-reset and email-verification tokens are valid for.
PASSWORD_RESET_TOKEN_TTL_HOURS = 1
EMAIL_VERIFICATION_TOKEN_TTL_HOURS = 24

# 2FA backup codes — number issued at setup. Each is single-use.
TOTP_BACKUP_CODE_COUNT = 10

# Pinned items per user. Cap is generous enough to be invisible in normal
# use but small enough that the dashboard widget never balloons.
MAX_PINNED_ITEMS = 12

# Researcher watchlist per user. Caps the JSON column's size.
MAX_WATCHLIST = 50

# Max researchers in a single bulk-analysis request — same shape
# constraint as source-check bulk to keep the worker pool predictable.
MAX_BULK_RESEARCHERS = 50

# Score buckets for the integrity-distribution chart and the top-issues card.
# Match the threshold convention used by lib/colors.ts on the frontend.
SCORE_HIGH_MIN = 70
SCORE_MEDIUM_MIN = 40
# AI-content threshold above which a check counts as "AI content detected"
# in top-issues aggregation.
AI_CONTENT_FLAG_THRESHOLD = 50.0
# How far back the team activity feed reaches.
TEAM_ACTIVITY_LOOKBACK_DAYS = 30
TEAM_ACTIVITY_MAX_ITEMS = 50
