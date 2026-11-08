from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class ResearcherAnalyzeRequest(BaseModel):
    researcher_name: Optional[str] = None
    scopus_id: Optional[str] = None
    google_scholar_id: Optional[str] = None
    orcid: Optional[str] = None


class PublicationAnalysisResponse(BaseModel):
    id: str
    title: str
    journal: Optional[str]
    year: Optional[int]
    doi: Optional[str]
    citation_count: int
    suspicious_citations: int
    topic_match_score: Optional[float]
    is_self_cited_heavily: bool
    flags: Optional[List[Any]]

    model_config = {"from_attributes": True}


class IntegrityDisclaimer(BaseModel):
    """Plain-language framing the UI must show alongside integrity scores
    and 'mutual citation pattern' findings. The strings live on the
    response (not just frontend copy) so the API contract carries the
    disclaimer — third-party clients and PDFs render the same caveats.

    `severity` distinguishes informational disclaimers from ones that must
    be displayed prominently before any "ring" / "manipulation" language.
    """

    severity: str  # "info" | "warning"
    headline: str
    body: str


# Default disclaimer text — single source of truth for both the API
# response and report PDFs. Word it carefully: this is the language a
# researcher's lawyer would read if a false-positive scoring triggered a
# reputational dispute.
DEFAULT_INTEGRITY_DISCLAIMER = IntegrityDisclaimer(
    severity="warning",
    headline="Patterns, not proof",
    body=(
        "Mutual-citation, self-citation, and topic-relevance findings are "
        "statistical patterns identified from publicly available bibliographic "
        "data. They flag relationships worth human review — they are not "
        "evidence of misconduct, do not establish intent, and should not be "
        "cited as conclusions. Field-specific norms, multi-disciplinary work, "
        "and gaps in source databases (notably Eastern European and non-English "
        "venues) can all produce signals that look like manipulation but aren't. "
        "Decisions should rest on independent expert review."
    ),
)


class ResearcherProfileResponse(BaseModel):
    id: str
    researcher_name: str
    scopus_id: Optional[str]
    google_scholar_id: Optional[str]
    orcid: Optional[str]
    institution: Optional[str]
    official_h_index: Optional[int]
    official_citation_count: Optional[int]
    adjusted_h_index: Optional[int]
    adjusted_citation_count: Optional[int]
    integrity_score: Optional[float]
    self_citation_rate: Optional[float]
    # Renamed in the UI as "Mutual citation patterns" — kept here on the
    # API for backwards compat with existing clients. See `disclaimer`
    # for the framing that must accompany this field.
    citation_ring_flags: Optional[Any]
    topic_relevance_score: Optional[float]
    analysis_status: str
    last_analyzed_at: Optional[datetime]
    created_at: datetime
    publications: List[PublicationAnalysisResponse] = []
    # Transparent integrity scoring — shaped per app.schemas.breakdown.IntegrityBreakdown.
    integrity_breakdown: Optional[Any] = None
    # Per-analysis governance — model used, fallbacks, processing warnings.
    model_metadata: Optional[Any] = None
    # The "patterns, not proof" framing the UI must surface before any
    # ring / manipulation language. Always populated on responses with
    # any integrity finding; null on profiles with no analysis yet.
    disclaimer: Optional[IntegrityDisclaimer] = None

    model_config = {"from_attributes": True}


class ResearcherListItem(BaseModel):
    id: str
    researcher_name: str
    institution: Optional[str]
    integrity_score: Optional[float]
    analysis_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ResearcherListResponse(BaseModel):
    items: List[ResearcherListItem]
    total: int
    page: int
    page_size: int


class CitationGraphResponse(BaseModel):
    nodes: List[Any]
    edges: List[Any]


# ─── Bulk submission ──────────────────────────────────────────────────────


class BulkResearcherCreate(BaseModel):
    items: List[ResearcherAnalyzeRequest]


class BulkResearcherResponse(BaseModel):
    """Returned from POST /bulk — frontend uses these ids to poll
    /batch?ids=… for progress."""

    batch_id: str
    items: List[ResearcherListItem]


# ─── Snapshots / history ──────────────────────────────────────────────────


class ResearcherSnapshotItem(BaseModel):
    id: str
    captured_at: Optional[datetime]
    created_at: datetime
    official_h_index: Optional[int] = None
    official_citation_count: Optional[int] = None
    adjusted_h_index: Optional[int] = None
    adjusted_citation_count: Optional[int] = None
    integrity_score: Optional[float] = None
    self_citation_rate: Optional[float] = None
    topic_relevance_score: Optional[float] = None
    total_publications: Optional[int] = None

    model_config = {"from_attributes": True}


# ─── Watchlist ────────────────────────────────────────────────────────────


class WatchlistEntry(BaseModel):
    """A hydrated watchlist row — current metrics + delta vs last snapshot."""

    researcher_id: str
    researcher_name: str
    institution: Optional[str] = None
    integrity_score: Optional[float] = None
    self_citation_rate: Optional[float] = None
    integrity_score_delta: Optional[float] = None  # current - previous; None if no prior snapshot
    last_analyzed_at: Optional[datetime] = None
    last_snapshot_at: Optional[datetime] = None
    added_at: datetime
