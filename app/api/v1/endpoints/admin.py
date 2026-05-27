import time
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentEmployeeDep, get_db_session
from app.services.metric_calculator import DEFAULT_WINDOW_DAYS, MetricCalculatorService

router = APIRouter(prefix="/admin", tags=["admin"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


class RecomputeMetricsResponse(BaseModel):
    processed_count: int
    took_ms: int
    window_days: int


@router.post("/recompute-metrics", response_model=RecomputeMetricsResponse)
async def recompute_metrics(
    session: SessionDep,
    _current_employee: CurrentEmployeeDep,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> RecomputeMetricsResponse:
    """Пересчитывает EmployeeMetric для всех сотрудников.

    Считает Ai, Ci, Li, Zi, Hi → Ri и UPSERT-ит строку в employee_metrics.
    Окно анализа фактических событий задаётся параметром `window_days`.
    """
    started_at = time.perf_counter()
    processed_count = await MetricCalculatorService(session).recompute_all(window_days=window_days)
    took_ms = int((time.perf_counter() - started_at) * 1000)
    return RecomputeMetricsResponse(
        processed_count=processed_count,
        took_ms=took_ms,
        window_days=window_days,
    )
