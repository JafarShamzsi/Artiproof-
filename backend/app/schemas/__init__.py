from app.schemas.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    UserUpdate,
    TokenResponse,
)
from app.schemas.source_check import (
    SourceCheckCreate,
    SourceCheckResponse,
    SourceCheckListItem,
    SourceCheckListResponse,
    ClaimAnalysisResponse,
    AIDetectionResponse,
    CitationCheckResponse,
)
from app.schemas.researcher import (
    ResearcherAnalyzeRequest,
    ResearcherProfileResponse,
    ResearcherListItem,
    ResearcherListResponse,
    PublicationAnalysisResponse,
    CitationGraphResponse,
)
from app.schemas.report import (
    ReportGenerateRequest,
    ReportResponse,
    ReportListResponse,
)
from app.schemas.dashboard import (
    DashboardStats,
    DashboardOverview,
    TrendResponse,
)

__all__ = [
    "UserRegister",
    "UserLogin",
    "UserResponse",
    "UserUpdate",
    "TokenResponse",
    "SourceCheckCreate",
    "SourceCheckResponse",
    "SourceCheckListItem",
    "SourceCheckListResponse",
    "ClaimAnalysisResponse",
    "AIDetectionResponse",
    "CitationCheckResponse",
    "ResearcherAnalyzeRequest",
    "ResearcherProfileResponse",
    "ResearcherListItem",
    "ResearcherListResponse",
    "PublicationAnalysisResponse",
    "CitationGraphResponse",
    "ReportGenerateRequest",
    "ReportResponse",
    "ReportListResponse",
    "DashboardStats",
    "DashboardOverview",
    "TrendResponse",
]
