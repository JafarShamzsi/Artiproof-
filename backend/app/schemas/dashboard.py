from pydantic import BaseModel
from typing import List, Any
from datetime import datetime


class DashboardStats(BaseModel):
    total_source_checks: int
    avg_credibility_score: float
    total_researcher_analyses: int
    recent_alerts: int


class RecentActivityItem(BaseModel):
    id: str
    type: str  # source_check or researcher_analysis
    title: str
    status: str
    score: float | None
    created_at: datetime


class DashboardOverview(BaseModel):
    stats: DashboardStats
    recent_activity: List[RecentActivityItem]


class TrendPoint(BaseModel):
    date: str
    score: float
    count: int


class TrendResponse(BaseModel):
    data: List[TrendPoint]
