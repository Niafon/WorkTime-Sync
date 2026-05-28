from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule_exception import ScheduleException
from app.repositories.employees import EmployeeRepository
from app.repositories.schedule_exceptions import ScheduleExceptionRepository
from app.schemas.schedule_exception import (
    ScheduleExceptionCreate,
    ScheduleExceptionUpdate,
)
from app.services.audit import (
    ACTION_CREATE,
    ACTION_DELETE,
    ACTION_UPDATE,
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

    async def update(
        self,
        employee_id: UUID,
        exception_id: UUID,
        payload: ScheduleExceptionUpdate,
        *,
        changed_by: UUID,
    ) -> ScheduleException:
        if await self.employees.get(employee_id) is None:
            raise NotFoundError("employee not found")
        schedule_exception = await self.exceptions.get(exception_id)
        if schedule_exception is None or schedule_exception.employee_id != employee_id:
            raise NotFoundError("schedule exception not found")

        before = exception_to_dict(schedule_exception)
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            raise InvalidOperationError("no fields to update")

        new_start = changes.get("start_dt", schedule_exception.start_dt)
        new_end = changes.get("end_dt", schedule_exception.end_dt)
        if new_start >= new_end:
            raise InvalidOperationError("start_dt must be earlier than end_dt")

        for field, value in changes.items():
            setattr(schedule_exception, field, value)
        await self.exceptions.flush()

        await record_change(
            self.session,
            entity_type=ENTITY_SCHEDULE_EXCEPTION,
            entity_id=schedule_exception.id,
            employee_id=employee_id,
            action=ACTION_UPDATE,
            changed_by=changed_by,
            before=before,
            after=exception_to_dict(schedule_exception),
        )
        await self.session.commit()
        return schedule_exception

    async def delete(
        self,
        employee_id: UUID,
        exception_id: UUID,
        *,
        changed_by: UUID,
    ) -> None:
        if await self.employees.get(employee_id) is None:
            raise NotFoundError("employee not found")
        schedule_exception = await self.exceptions.get(exception_id)
        if schedule_exception is None or schedule_exception.employee_id != employee_id:
            raise NotFoundError("schedule exception not found")

        before = exception_to_dict(schedule_exception)
        await self.exceptions.delete(schedule_exception)
        await record_change(
            self.session,
            entity_type=ENTITY_SCHEDULE_EXCEPTION,
            entity_id=exception_id,
            employee_id=employee_id,
            action=ACTION_DELETE,
            changed_by=changed_by,
            before=before,
        )
        await self.session.commit()
