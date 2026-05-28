from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.analytics import (
    ActualityHistoryPoint,
    RiskDistributionPoint,
    SummaryDeltasResponse,
    TeamMetricsHistoryPoint,
    TeamRatingItem,
)
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/actuality-history", response_model=list[ActualityHistoryPoint])
async def get_actuality_history(
    session: SessionDep,
    months: int = Query(6, ge=1, le=24),
) -> list[ActualityHistoryPoint]:
    """Динамика среднего Ai по месяцам (ТЗ §14)."""
    return await AnalyticsService(session).actuality_history(months=months)


@router.get("/risk-distribution-history", response_model=list[RiskDistributionPoint])
async def get_risk_distribution_history(
    session: SessionDep,
    months: int = Query(6, ge=1, le=24),
) -> list[RiskDistributionPoint]:
    """Распределение сотрудников по risk_level по месяцам."""
    return await AnalyticsService(session).risk_distribution_history(months=months)


@router.get("/team-rating", response_model=list[TeamRatingItem])
async def get_team_rating(
    session: SessionDep,
    limit: int = Query(10, ge=1, le=100),
) -> list[TeamRatingItem]:
    """Рейтинг команд: по возрастанию avg_actuality, затем по убыванию avg_risk_score."""
    return await AnalyticsService(session).team_rating(limit=limit)


@router.get("/summary-deltas", response_model=SummaryDeltasResponse)
async def get_summary_deltas(
    session: SessionDep,
    period: Literal["month", "week"] = "month",
) -> SummaryDeltasResponse:
    """Дельты Ai/Ci/outdated за период vs предыдущий период."""
    return await AnalyticsService(session).summary_deltas(period=period)


@router.get(
    "/teams/{team_id}/metrics-history",
    response_model=list[TeamMetricsHistoryPoint],
)
async def get_team_metrics_history(
    team_id: UUID,
    session: SessionDep,
    months: int = Query(6, ge=1, le=24),
) -> list[TeamMetricsHistoryPoint]:
    """Динамика метрик команды по месяцам: Ai, Ri, attention_count."""
    return await AnalyticsService(session).team_metrics_history(team_id, months)
