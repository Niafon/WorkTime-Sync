from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select, tuple_
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
                or_(
                    ActivityEvent.end_dt > range_start,
                    ActivityEvent.recurrence_rule.is_not(None),
                ),
            )
            .order_by(ActivityEvent.start_dt)
        )
        return list(result.scalars().all())

    async def get(self, event_id: UUID) -> ActivityEvent | None:
        return await self.session.get(ActivityEvent, event_id)

    async def list_conflicts(
        self,
        *,
        employee_ids: list[UUID] | None = None,
        range_start: datetime | None = None,
        range_end: datetime | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ActivityEvent]:
        query = select(ActivityEvent).where(ActivityEvent.is_outside_schedule.is_(True))
        if employee_ids is not None:
            if not employee_ids:
                return []
            query = query.where(ActivityEvent.employee_id.in_(employee_ids))
        if range_end is not None:
            query = query.where(ActivityEvent.start_dt < range_end)
        if range_start is not None:
            query = query.where(ActivityEvent.end_dt > range_start)
        if search:
            query = query.where(ActivityEvent.title.ilike(f"%{search}%"))
        query = query.order_by(ActivityEvent.start_dt.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_conflicts(
        self,
        *,
        employee_ids: list[UUID] | None = None,
        range_start: datetime | None = None,
        range_end: datetime | None = None,
        search: str | None = None,
    ) -> int:
        query = select(func.count()).select_from(ActivityEvent).where(
            ActivityEvent.is_outside_schedule.is_(True)
        )
        if employee_ids is not None:
            if not employee_ids:
                return 0
            query = query.where(ActivityEvent.employee_id.in_(employee_ids))
        if range_end is not None:
            query = query.where(ActivityEvent.start_dt < range_end)
        if range_start is not None:
            query = query.where(ActivityEvent.end_dt > range_start)
        if search:
            query = query.where(ActivityEvent.title.ilike(f"%{search}%"))
        result = await self.session.execute(query)
        return int(result.scalar_one())
