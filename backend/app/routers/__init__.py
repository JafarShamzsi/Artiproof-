from app.routers.analytics import router as analytics_router
from app.routers.auth import router as auth_router
from app.routers.dashboard import router as dashboard_router
from app.routers.reports import router as reports_router
from app.routers.researcher import router as researcher_router
from app.routers.security import router as security_router
from app.routers.source_check import router as source_check_router

__all__ = [
    "analytics_router",
    "auth_router",
    "dashboard_router",
    "reports_router",
    "researcher_router",
    "security_router",
    "source_check_router",
]
