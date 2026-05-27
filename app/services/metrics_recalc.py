from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.metrics import (
    actuality_score,
    days_since_update,
    risk_level,
    risk_score,
)
from app.repositories.employee_metrics import EmployeeMetricRepository
from app.repositories.work_schedules import WorkScheduleRepository


async def recalc_actuality(session: AsyncSession, employee_id: UUID) -> None:
    """Частичный пересчёт актуальности сотрудника после подтверждения графика.

    Обновляются только поля, связанные с d_i и A_i (плюс производный risk).
    Остальные компоненты (conflict_rate, load_level, zone/hr factors) сохраняются.
    Коммит остаётся за вызывающим кодом.
    """
    metric_repo = EmployeeMetricRepository(session)
    schedule_repo = WorkScheduleRepository(session)

    metric = await metric_repo.get_for_employee(employee_id)
    if metric is None:
        return
    schedule = await schedule_repo.get_active_for_employee(employee_id)
    if schedule is None:
        return

    now = datetime.now(timezone.utc)
    new_days = days_since_update(
        schedule.last_updated_at,
        now.date(),
        confirmed_at=schedule.confirmed_at,
    )
    new_actuality = actuality_score(new_days)
    new_risk = risk_score(
        actuality_score_value=new_actuality,
        conflict_rate_value=metric.conflict_rate,
        load_level_value=metric.load_level,
        zone_factor_value=metric.zone_factor,
        hr_factor_value=metric.hr_factor,
    )

    metric.days_since_update = new_days
    metric.actuality_score = new_actuality
    metric.risk_score = new_risk
    metric.risk_level = risk_level(new_risk)
    metric.calculated_at = now
    await session.flush()
