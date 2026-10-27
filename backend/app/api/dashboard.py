from fastapi import APIRouter, Depends, Query

from ..schema.auth import CurrentUser
from ..schema.dashboard import DashboardOut
from ..services.analytics import AnalyticsService
from .deps import get_analytics_service, get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def dashboard(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    months: int = Query(default=6, ge=1, le=24),
    user: CurrentUser = Depends(get_current_user),
    analytics: AnalyticsService = Depends(get_analytics_service),
):
    return analytics.dashboard(user.id, month, months)
