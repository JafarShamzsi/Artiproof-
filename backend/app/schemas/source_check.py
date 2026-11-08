from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class SourceCheckCreate(BaseModel):
    input_type: str  # url, text, document
    input_content: str


class ClaimAnalysisResponse(BaseModel):
    id: str
    claim_text: str
    verdict: str
    confidence: float
    explanation: str
    true_version: Optional[str]
    sources: Optional[List[Any]]
    origin_trace: Optional[Any]
    position_in_text: Optional[Any]

    model_config = {"from_attributes": True}


class AIDetectionResponse(BaseModel):
    id: str
    paragraph_index: int
    paragraph_text: str
    ai_probability: float
    detection_method: str

    model_config = {"from_attributes": True}


class CitationCheckResponse(BaseModel):
    id: str
    original_citation: str
    citation_url: Optional[str]
    is_accessible: bool
    is_retracted: bool
    credibility_score: Optional[float]
    issues: Optional[List[Any]]
    suggested_alternative: Optional[str]

    model_config = {"from_attributes": True}


class CoverageNote(BaseModel):
    """A single coverage caveat the UI should surface — e.g. text truncation
    or paragraph capping. Shape stays additive: new caveat types just add
    new ``kind`` values, frontend renders unknowns generically."""

    kind: str  # "text_truncated" | "claims_capped" | "paragraphs_capped" | "fallback_heuristic" | ...
    severity: str  # "info" | "warning"
    headline: str  # short human label, ≤ 60 chars
    detail: str  # one-sentence explanation, ≤ 200 chars


class CoverageSummary(BaseModel):
    """Derived from model_metadata. Surfaces *what the analysis didn't see*
    so the user knows the score reflects partial input. Empty `notes` =
    full-coverage analysis."""

    notes: List[CoverageNote] = []
    # Headline numbers for the top-of-report band, e.g. "15 of 47 claims".
    claims_analyzed: Optional[int] = None
    claims_extracted: Optional[int] = None
    paragraphs_analyzed: Optional[int] = None
    paragraphs_total: Optional[int] = None
    text_chars_analyzed: Optional[int] = None
    text_chars_total: Optional[int] = None


class SourceCheckResponse(BaseModel):
    id: str
    user_id: str
    input_type: str
    input_content: str
    input_title: Optional[str]
    status: str
    overall_credibility_score: Optional[float]
    ai_content_percentage: Optional[float]
    misinfo_claims_found: Optional[int]
    has_pdf: bool = False
    has_annotated_pdf: bool = False
    created_at: datetime
    completed_at: Optional[datetime]
    claims: List[ClaimAnalysisResponse] = []
    ai_detections: List[AIDetectionResponse] = []
    citations: List[CitationCheckResponse] = []
    # Transparent scoring — JSON blob shaped per app.schemas.breakdown.ScoreBreakdown.
    # Optional Any to avoid coupling the response schema to the breakdown's internal shape.
    score_breakdown: Optional[Any] = None
    # Per-analysis governance record — model used, fallbacks, processing warnings.
    model_metadata: Optional[Any] = None
    # Coverage caveats derived from model_metadata.processing_warnings — what
    # the analysis sampled vs the total input. Used by the UI to render
    # "analyzed N of M claims" / "first 15K of 73K chars" banners.
    coverage: Optional[CoverageSummary] = None
    # Public share token, when one has been issued (otherwise None). Lets the
    # frontend decide between "Create share link" and "Copy share link" CTAs
    # without needing to call POST /share-token (which would auto-create).
    share_token: Optional[str] = None

    model_config = {"from_attributes": True}


class SourceCheckListItem(BaseModel):
    id: str
    input_type: str
    input_title: Optional[str]
    status: str
    overall_credibility_score: Optional[float]
    ai_content_percentage: Optional[float]
    misinfo_claims_found: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceCheckListResponse(BaseModel):
    items: List[SourceCheckListItem]
    total: int
    page: int
    page_size: int


# ─── Bulk submission ──────────────────────────────────────────────────────


class BulkSourceCheckItem(BaseModel):
    input_type: str  # "url" | "text"
    input_content: str


class BulkSourceCheckCreate(BaseModel):
    items: List[BulkSourceCheckItem]


class BulkSourceCheckResponse(BaseModel):
    """Returned from POST /bulk — the frontend uses these ids to poll
    /batch?ids=… for progress."""

    batch_id: str
    items: List[SourceCheckListItem]


# ─── Share token ──────────────────────────────────────────────────────────


class ShareTokenResponse(BaseModel):
    share_token: str
    share_url: str  # absolute, e.g. https://example.invalid/check/shared/<token>


class SharedSourceCheckResponse(BaseModel):
    """Public view — same shape as SourceCheckResponse minus user_id and
    minus input_content for URL-type checks (the URL is the secret)."""

    id: str
    input_type: str
    input_title: Optional[str]
    status: str
    overall_credibility_score: Optional[float]
    ai_content_percentage: Optional[float]
    misinfo_claims_found: Optional[int]
    has_pdf: bool = False
    has_annotated_pdf: bool = False
    created_at: datetime
    completed_at: Optional[datetime]
    claims: List[ClaimAnalysisResponse] = []
    ai_detections: List[AIDetectionResponse] = []
    citations: List[CitationCheckResponse] = []
    score_breakdown: Optional[Any] = None
    coverage: Optional[CoverageSummary] = None

    model_config = {"from_attributes": True}
