from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schedule_exception import ScheduleException
from app.repositories.employees import EmployeeRepository
from app.repositories.schedule_exceptions import ScheduleExceptionRepository
from app.schemas.schedule_exception import ScheduleExceptionCreate
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
    ) -> ScheduleException:
        if payload.employee_id != employee_id:
            raise InvalidOperationError("employee_id in path and body must match")
        if await self.employees.get(employee_id) is None:
            raise NotFoundError("employee not found")

        schedule_exception = await self.exceptions.create(ScheduleException(**payload.model_dump()))
        await self.session.commit()
        return schedule_exception

    async def list_for_employee(self, employee_id: UUID) -> list[ScheduleException]:
        if await self.employees.get(employee_id) is None:
            raise NotFoundError("employee not found")
        return await self.exceptions.list_for_employee(employee_id)
