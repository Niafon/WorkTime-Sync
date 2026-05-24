from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule_exception import ScheduleException


class ScheduleExceptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, schedule_exception: ScheduleException) -> ScheduleException:
        self.session.add(schedule_exception)
        await self.session.flush()
        await self.session.refresh(schedule_exception)
        return schedule_exception

    async def list_for_employee(self, employee_id: UUID) -> list[ScheduleException]:
        result = await self.session.execute(
            select(ScheduleException)
            .where(ScheduleException.employee_id == employee_id)
            .order_by(ScheduleException.start_dt.desc())
        )
        return list(result.scalars().all())

    async def list_for_employees_in_range(
        self,
        employee_ids: list[UUID],
        range_start: datetime,
        range_end: datetime,
    ) -> list[ScheduleException]:
        if not employee_ids:
            return []
        result = await self.session.execute(
            select(ScheduleException)
            .where(
                ScheduleException.employee_id.in_(employee_ids),
                ScheduleException.start_dt < range_end,
                ScheduleException.end_dt > range_start,
            )
            .order_by(ScheduleException.start_dt)
        )
        return list(result.scalars().all())
