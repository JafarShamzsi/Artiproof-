from app.routers.analytics import router as analytics_router
from app.routers.auth import router as auth_router
from app.routers.dashboard import router as dashboard_router
from app.routers.organizations import router as organizations_router
from app.routers.report_schedules import router as report_schedules_router
from app.routers.reports import router as reports_router
from app.routers.researcher import router as researcher_router
from app.routers.researcher import watchlist_router
from app.routers.security import router as security_router
from app.routers.source_check import router as source_check_router

__all__ = [
    "analytics_router",
    "auth_router",
    "dashboard_router",
    "organizations_router",
    "report_schedules_router",
    "reports_router",
    "researcher_router",
    "security_router",
    "source_check_router",
    "watchlist_router",
]
