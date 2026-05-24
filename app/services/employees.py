from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.repositories.employees import EmployeeRepository
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.services.exceptions import InvalidOperationError, NotFoundError


class EmployeeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.employees = EmployeeRepository(session)

    async def create(self, payload: EmployeeCreate) -> Employee:
        employee = Employee(**payload.model_dump())
        try:
            employee = await self.employees.create(employee)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise InvalidOperationError(
                "employee with this email or VK user id already exists"
            ) from exc
        return employee

    async def list(self) -> list[Employee]:
        return await self.employees.list()

    async def get(self, employee_id: UUID) -> Employee:
        employee = await self.employees.get(employee_id)
        if employee is None:
            raise NotFoundError("employee not found")
        return employee

    async def update(self, employee_id: UUID, payload: EmployeeUpdate) -> Employee:
        employee = await self.get(employee_id)
        values = payload.model_dump(exclude_unset=True)
        try:
            employee = await self.employees.update(employee, values)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise InvalidOperationError(
                "employee with this email or VK user id already exists"
            ) from exc
        return employee
