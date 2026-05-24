from datetime import datetime
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_event import ActivityEvent


class ActivityEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, event: ActivityEvent) -> ActivityEvent:
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def find_by_external_id(self, source: str, external_id: str) -> ActivityEvent | None:
        result = await self.session.execute(
            select(ActivityEvent).where(
                ActivityEvent.source == source,
                ActivityEvent.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_existing_external_keys(self, keys: set[tuple[str, str]]) -> set[tuple[str, str]]:
        if not keys:
            return set()
        result = await self.session.execute(
            select(ActivityEvent.source, ActivityEvent.external_id).where(
                tuple_(ActivityEvent.source, ActivityEvent.external_id).in_(keys)
            )
        )
        return {
            (source, external_id)
            for source, external_id in result.all()
            if external_id is not None
        }

    async def list_for_employee(self, employee_id: UUID) -> list[ActivityEvent]:
        result = await self.session.execute(
            select(ActivityEvent)
            .where(ActivityEvent.employee_id == employee_id)
            .order_by(ActivityEvent.start_dt.desc())
        )
        return list(result.scalars().all())

    async def list_for_employees(self, employee_ids: list[UUID]) -> list[ActivityEvent]:
        if not employee_ids:
            return []
        result = await self.session.execute(
            select(ActivityEvent)
            .where(ActivityEvent.employee_id.in_(employee_ids))
            .order_by(ActivityEvent.start_dt.desc())
        )
        return list(result.scalars().all())

    async def list_for_employees_in_range(
        self,
        employee_ids: list[UUID],
        range_start: datetime,
        range_end: datetime,
    ) -> list[ActivityEvent]:
        if not employee_ids:
            return []
        result = await self.session.execute(
            select(ActivityEvent)
            .where(
                ActivityEvent.employee_id.in_(employee_ids),
                ActivityEvent.start_dt < range_end,
                ActivityEvent.end_dt > range_start,
            )
            .order_by(ActivityEvent.start_dt)
        )
        return list(result.scalars().all())
