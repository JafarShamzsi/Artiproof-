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
