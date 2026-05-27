from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.schedule_confirmation_request import (
    CONFIRMATION_STATUS_CONFIRMED,
    CONFIRMATION_STATUS_PENDING,
    ScheduleConfirmationRequest,
)


class ScheduleConfirmationRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        request: ScheduleConfirmationRequest,
    ) -> ScheduleConfirmationRequest:
        self.session.add(request)
        await self.session.flush()
        await self.session.refresh(request)
        return request

    async def get_by_id(
        self,
        request_id: UUID,
    ) -> ScheduleConfirmationRequest | None:
        result = await self.session.execute(
            select(ScheduleConfirmationRequest)
            .options(
                selectinload(ScheduleConfirmationRequest.employee),
                selectinload(ScheduleConfirmationRequest.requested_by),
            )
            .where(ScheduleConfirmationRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def list_by_employee(
        self,
        employee_id: UUID,
        status_filter: str | None = None,
    ) -> list[ScheduleConfirmationRequest]:
        stmt = (
            select(ScheduleConfirmationRequest)
            .options(
                selectinload(ScheduleConfirmationRequest.employee),
                selectinload(ScheduleConfirmationRequest.requested_by),
            )
            .where(ScheduleConfirmationRequest.employee_id == employee_id)
            .order_by(ScheduleConfirmationRequest.created_at.desc())
        )
        if status_filter is not None:
            stmt = stmt.where(ScheduleConfirmationRequest.status == status_filter)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_for_employee(
        self,
        employee_id: UUID,
    ) -> ScheduleConfirmationRequest | None:
        result = await self.session.execute(
            select(ScheduleConfirmationRequest)
            .options(
                selectinload(ScheduleConfirmationRequest.employee),
                selectinload(ScheduleConfirmationRequest.requested_by),
            )
            .where(
                ScheduleConfirmationRequest.employee_id == employee_id,
                ScheduleConfirmationRequest.status == CONFIRMATION_STATUS_PENDING,
            )
            .order_by(ScheduleConfirmationRequest.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def mark_all_pending_as_confirmed(
        self,
        employee_id: UUID,
        now: datetime | None = None,
    ) -> list[UUID]:
        now = now or datetime.now(timezone.utc)
        result = await self.session.execute(
            select(ScheduleConfirmationRequest).where(
                ScheduleConfirmationRequest.employee_id == employee_id,
                ScheduleConfirmationRequest.status == CONFIRMATION_STATUS_PENDING,
            )
        )
        closed: list[UUID] = []
        for request in result.scalars().all():
            request.status = CONFIRMATION_STATUS_CONFIRMED
            request.responded_at = now
            closed.append(request.id)
        await self.session.flush()
        return closed
