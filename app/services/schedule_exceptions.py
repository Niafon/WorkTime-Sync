from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule_exception import ScheduleException
from app.repositories.employees import EmployeeRepository
from app.repositories.schedule_exceptions import ScheduleExceptionRepository
from app.schemas.schedule_exception import ScheduleExceptionCreate
from app.services.audit import (
    ACTION_CREATE,
    ENTITY_SCHEDULE_EXCEPTION,
    exception_to_dict,
    record_change,
)
from app.services.exceptions import InvalidOperationError, NotFoundError


class ScheduleExceptionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.employees = EmployeeRepository(session)
        self.exceptions = ScheduleExceptionRepository(session)

    async def create(
        self,
        employee_id: UUID,
        payload: ScheduleExceptionCreate,
        *,
        changed_by: UUID,
    ) -> ScheduleException:
        if payload.employee_id != employee_id:
            raise InvalidOperationError("employee_id in path and body must match")
        if await self.employees.get(employee_id) is None:
            raise NotFoundError("employee not found")

        schedule_exception = await self.exceptions.create(ScheduleException(**payload.model_dump()))
        await record_change(
            self.session,
            entity_type=ENTITY_SCHEDULE_EXCEPTION,
            entity_id=schedule_exception.id,
            employee_id=employee_id,
            action=ACTION_CREATE,
            changed_by=changed_by,
            after=exception_to_dict(schedule_exception),
        )
        await self.session.commit()
        return schedule_exception

    async def list_for_employee(self, employee_id: UUID) -> list[ScheduleException]:
        if await self.employees.get(employee_id) is None:
            raise NotFoundError("employee not found")
        return await self.exceptions.list_for_employee(employee_id)
