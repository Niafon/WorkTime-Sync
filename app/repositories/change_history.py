from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.change_history import ChangeHistory


class ChangeHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, entry: ChangeHistory) -> ChangeHistory:
        self.session.add(entry)
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def list_for_employee(
        self,
        employee_id: UUID,
        *,
        entity_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ChangeHistory]:
        stmt = select(ChangeHistory).where(ChangeHistory.employee_id == employee_id)
        if entity_type is not None:
            stmt = stmt.where(ChangeHistory.entity_type == entity_type)
        stmt = stmt.order_by(ChangeHistory.changed_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
