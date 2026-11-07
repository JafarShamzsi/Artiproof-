"""Pydantic schemas for the score_breakdown / integrity_breakdown JSON blobs.

These are the contract the frontend reads when displaying "why this score?".
Stored as JSON in the DB (SourceCheck.score_breakdown,
ResearcherProfile.integrity_breakdown) so they're not enforced at insert
time — but every code path that writes them should produce values matching
these shapes.

Bumping FORMULA_VERSION is the signal that historical breakdowns are no
longer comparable (e.g. weights changed). Old breakdowns keep their old
formula_version for traceability.
"""

from typing import Any, Optional

from pydantic import BaseModel

FORMULA_VERSION = "1.0"


class Deduction(BaseModel):
    reason: str
    impact: float
    detail: dict[str, Any] = {}


class ScoreBreakdown(BaseModel):
    base: float = 100.0
    deductions: list[Deduction] = []
    warnings: list[str] = []
    final: float
    confidence: Optional[float] = None
    formula_version: str = FORMULA_VERSION


class IntegrityAdjustment(BaseModel):
    reason: str
    impact: float
    detail: dict[str, Any] = {}


class IntegrityBreakdown(BaseModel):
    base: float = 100.0
    adjustments: list[IntegrityAdjustment] = []
    warnings: list[str] = []
    final: float
    confidence: Optional[float] = None
    formula_version: str = FORMULA_VERSION


class ModelMetadata(BaseModel):
    """Per-analysis governance record. Lets us debug why a particular
    analysis produced its result.
    """

    model_provider: str
    model_name: str
    apis_used: list[str] = []
    fallback_used: bool = False
    processing_warnings: list[dict[str, Any]] = []
    timestamp: str  # ISO 8601 UTC
    formula_version: str = FORMULA_VERSION
    # Free-form per-analysis context (text length, paragraphs, etc.)
    context: dict[str, Any] = {}
