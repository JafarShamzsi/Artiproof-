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
