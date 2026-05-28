from collections import Counter
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_event import ActivityEvent
from app.repositories.employee_metrics import EmployeeMetricRepository
from app.repositories.employees import EmployeeRepository
from app.schemas.schedule_diagnostics import ScheduleDiagnosticsResponse
from app.services.exceptions import NotFoundError

DIAGNOSTICS_WINDOW_DAYS = 30
ALERT_OUTSIDE_RATIO_THRESHOLD = 0.20
ALERT_DAYS_SINCE_UPDATE_THRESHOLD = 60
ZONE_DRIFT_THRESHOLD = 0.20


class ScheduleDiagnosticsService:
    """Считает данные для алёрта «Обнаружено расхождение» на /my/schedule.

    Источник истины — кэшированный `EmployeeMetric`. «Самый частый час
    out-of-hours встреч» досчитываем здесь же по `activity_events`, так как
    в метриках хранится только суммарное число.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.employees = EmployeeRepository(session)
        self.metrics = EmployeeMetricRepository(session)

    async def get_for_employee(self, employee_id: UUID) -> ScheduleDiagnosticsResponse:
        if await self.employees.get(employee_id) is None:
            raise NotFoundError("employee not found")

        metric = await self.metrics.get_for_employee(employee_id)
        outside_events = metric.outside_events_count if metric is not None else 0
        total_events = metric.total_events_count if metric is not None else 0
        days_since_update = metric.days_since_update if metric is not None else 0
        zone_factor = metric.zone_factor if metric is not None else 0.0

        outside_after_hour = await self._mode_outside_hour(employee_id)

        should_show_alert = (
            outside_events > 0
            and (
                total_events == 0
                or outside_events / total_events >= ALERT_OUTSIDE_RATIO_THRESHOLD
            )
        ) or days_since_update >= ALERT_DAYS_SINCE_UPDATE_THRESHOLD

        return ScheduleDiagnosticsResponse(
            window_days=DIAGNOSTICS_WINDOW_DAYS,
            total_events=total_events,
            outside_events=outside_events,
            outside_after_hour=outside_after_hour,
            has_timezone_drift=zone_factor >= ZONE_DRIFT_THRESHOLD,
            days_since_update=days_since_update,
            should_show_alert=should_show_alert,
        )

    async def _mode_outside_hour(self, employee_id: UUID) -> int | None:
        # Час берётся в UTC (как хранится TIMESTAMP WITH TIME ZONE), а не в TZ
        # сотрудника — для MVP-алёрта «активность после 19:00» этого хватает
        # для большинства московских кейсов; точная локализация может быть
        # добавлена позже.
        window_end = datetime.now(UTC)
        window_start = window_end - timedelta(days=DIAGNOSTICS_WINDOW_DAYS)
        result = await self.session.execute(
            select(ActivityEvent.start_dt).where(
                ActivityEvent.employee_id == employee_id,
                ActivityEvent.is_outside_schedule.is_(True),
                ActivityEvent.start_dt >= window_start,
                ActivityEvent.start_dt < window_end,
            )
        )
        hours = [dt.hour for dt in result.scalars().all()]
        if not hours:
            return None
        most_common_hour, _ = Counter(hours).most_common(1)[0]
        return most_common_hour
