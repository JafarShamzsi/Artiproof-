from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# Templates supported by the report renderer. The default `"full"` is the
# original detailed source-check / researcher report. Executive summary is
# 1-page condensed; comparison spans multiple source checks; institutional
# audit spans multiple researchers.
ReportTemplate = Literal[
    "full",
    "executive_summary",
    "comparison",
    "institutional_audit",
]


class ReportGenerateRequest(BaseModel):
    template: ReportTemplate = "full"

    # Single-record templates ("full", "executive_summary") use one of these.
    source_check_id: Optional[str] = None
    researcher_profile_id: Optional[str] = None

    # Multi-record templates use these arrays. Comparison takes source check
    # ids; institutional audit takes researcher profile ids. Each id is
    # ownership-checked at the route level.
    source_check_ids: Optional[List[str]] = None
    researcher_profile_ids: Optional[List[str]] = None


class ReportAnnotation(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class ReportAnnotationsUpdate(BaseModel):
    annotations: List[ReportAnnotation]

    @field_validator("annotations")
    @classmethod
    def cap_count(cls, v: List[ReportAnnotation]) -> List[ReportAnnotation]:
        if len(v) > 50:
            raise ValueError("Too many annotations (max 50)")
        return v


class ReportResponse(BaseModel):
    id: str
    user_id: str
    source_check_id: Optional[str]
    researcher_profile_id: Optional[str]
    report_type: str
    template: str = "full"
    title: str
    summary: Optional[str]
    pdf_path: Optional[str]
    share_token: str
    annotations: Optional[List[Any]] = None
    source_check_ids: Optional[List[str]] = None
    researcher_profile_ids: Optional[List[str]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    items: List[ReportResponse]
    total: int
    page: int
    page_size: int


# ─── Schedules ────────────────────────────────────────────────────────────


ReportFrequency = Literal["weekly", "monthly"]


class ReportScheduleCreate(BaseModel):
    frequency: ReportFrequency
    template: ReportTemplate = "executive_summary"


class ReportScheduleResponse(BaseModel):
    id: str
    user_id: str
    frequency: str
    template: str
    active: bool
    last_run_at: Optional[datetime]
    next_run_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportScheduleUpdate(BaseModel):
    active: Optional[bool] = None
    frequency: Optional[ReportFrequency] = None
    template: Optional[ReportTemplate] = None


# ─── Branding (white-label) ───────────────────────────────────────────────


class OrganizationBranding(BaseModel):
    logo_url: Optional[str] = Field(None, max_length=2000)
    primary_color: Optional[str] = Field(None, max_length=16)
    secondary_color: Optional[str] = Field(None, max_length=16)

    @field_validator("primary_color", "secondary_color")
    @classmethod
    def hex_color(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        # Loose validation — allow #RGB, #RRGGBB, or named colors.
        if not v.startswith("#") and not v.replace("-", "").isalpha():
            raise ValueError("Invalid color format")
        return v


class OrganizationBrandingResponse(BaseModel):
    id: str
    name: str
    logo_url: Optional[str]
    primary_color: Optional[str]
    secondary_color: Optional[str]

    model_config = {"from_attributes": True}
