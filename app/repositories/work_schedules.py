from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work_schedule import WorkSchedule


class WorkScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, schedule: WorkSchedule) -> WorkSchedule:
        self.session.add(schedule)
        await self.session.flush()
        await self.session.refresh(schedule)
        return schedule

    async def get_active_for_employee(self, employee_id: UUID) -> WorkSchedule | None:
        result = await self.session.execute(
            select(WorkSchedule)
            .where(WorkSchedule.employee_id == employee_id, WorkSchedule.is_active.is_(True))
            .order_by(WorkSchedule.last_updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_active_for_employees(self, employee_ids: list[UUID]) -> list[WorkSchedule]:
        if not employee_ids:
            return []
        result = await self.session.execute(
            select(WorkSchedule).where(
                WorkSchedule.employee_id.in_(employee_ids),
                WorkSchedule.is_active.is_(True),
            )
        )
        return list(result.scalars().all())
