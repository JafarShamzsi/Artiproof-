from app.routers.auth import router as auth_router
from app.routers.source_check import router as source_check_router
from app.routers.researcher import router as researcher_router
from app.routers.reports import router as reports_router
from app.routers.dashboard import router as dashboard_router

__all__ = [
    "auth_router",
    "source_check_router",
    "researcher_router",
    "reports_router",
    "dashboard_router",
]
