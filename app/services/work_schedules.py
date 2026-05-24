from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work_schedule import WorkSchedule
from app.repositories.employees import EmployeeRepository
from app.repositories.work_schedules import WorkScheduleRepository
from app.schemas.work_schedule import WorkScheduleCreate
from app.services.exceptions import InvalidOperationError, NotFoundError


class WorkScheduleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.employees = EmployeeRepository(session)
        self.schedules = WorkScheduleRepository(session)

    async def create(self, employee_id: UUID, payload: WorkScheduleCreate) -> WorkSchedule:
        if payload.employee_id != employee_id:
            raise InvalidOperationError("employee_id in path and body must match")
        if await self.employees.get(employee_id) is None:
            raise NotFoundError("employee not found")

        schedule = await self.schedules.create(WorkSchedule(**payload.model_dump()))
        await self.session.commit()
        return schedule

    async def get_active(self, employee_id: UUID) -> WorkSchedule:
        if await self.employees.get(employee_id) is None:
            raise NotFoundError("employee not found")
        schedule = await self.schedules.get_active_for_employee(employee_id)
        if schedule is None:
            raise NotFoundError("active schedule not found")
        return schedule
