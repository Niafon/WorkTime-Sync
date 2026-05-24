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
