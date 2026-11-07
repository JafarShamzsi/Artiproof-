from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ReportGenerateRequest(BaseModel):
    source_check_id: Optional[str] = None
    researcher_profile_id: Optional[str] = None


class ReportResponse(BaseModel):
    id: str
    user_id: str
    source_check_id: Optional[str]
    researcher_profile_id: Optional[str]
    report_type: str
    title: str
    summary: Optional[str]
    pdf_path: Optional[str]
    share_token: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    items: List[ReportResponse]
    total: int
    page: int
    page_size: int
