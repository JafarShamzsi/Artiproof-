"""Status enum types shared between models and Alembic migrations.

Values are lowercase to match the strings already stored in the DB
(e.g. "pending", "completed"). Using `str, Enum` lets call sites continue
to assign string literals while gaining type safety where consumers want it.
"""

import enum


class CheckStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class AnalysisStatus(str, enum.Enum):
    pending = "pending"
    scraping = "scraping"
    processing = "processing"
    analyzing = "analyzing"
    completed = "completed"
    failed = "failed"
