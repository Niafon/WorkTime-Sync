from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee_metric import EmployeeMetric


class EmployeeMetricRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_employee(self, employee_id: UUID) -> EmployeeMetric | None:
        result = await self.session.execute(
            select(EmployeeMetric).where(EmployeeMetric.employee_id == employee_id)
        )
        return result.scalar_one_or_none()

    async def list_for_employees(self, employee_ids: list[UUID]) -> list[EmployeeMetric]:
        if not employee_ids:
            return []
        result = await self.session.execute(
            select(EmployeeMetric).where(EmployeeMetric.employee_id.in_(employee_ids))
        )
        return list(result.scalars().all())

    async def upsert(self, metric: EmployeeMetric) -> EmployeeMetric:
        existing = await self.get_for_employee(metric.employee_id)
        if existing is None:
            self.session.add(metric)
            await self.session.flush()
            await self.session.refresh(metric)
            return metric
        existing.calculated_at = metric.calculated_at
        existing.days_since_update = metric.days_since_update
        existing.actuality_score = metric.actuality_score
        existing.outside_events_count = metric.outside_events_count
        existing.total_events_count = metric.total_events_count
        existing.conflict_rate = metric.conflict_rate
        existing.load_level = metric.load_level
        existing.zone_factor = metric.zone_factor
        existing.hr_factor = metric.hr_factor
        existing.risk_score = metric.risk_score
        existing.risk_level = metric.risk_level
        await self.session.flush()
        await self.session.refresh(existing)
        return existing
