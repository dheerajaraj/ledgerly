from fastapi import APIRouter, Depends, Query

from ..schema.auth import CurrentUser
from ..schema.insights import AskIn, AskOut, SummaryOut
from ..services.insights_service import InsightsService
from .deps import get_current_user, get_insights_service

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.post("/summary", response_model=SummaryOut)
def summary(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    user: CurrentUser = Depends(get_current_user),
    insights: InsightsService = Depends(get_insights_service),
):
    return insights.monthly_summary(user.id, month)


@router.post("/ask", response_model=AskOut)
def ask(body: AskIn, user: CurrentUser = Depends(get_current_user), insights: InsightsService = Depends(get_insights_service)):
    return insights.ask(user.id, body.question)
