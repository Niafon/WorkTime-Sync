from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee
from app.repositories.employees import EmployeeRepository
from app.schemas.employee import EmployeeCreate, EmployeeUpdate
from app.services.audit import (
    ACTION_UPDATE,
    ENTITY_EMPLOYEE,
    employee_to_dict,
    record_change,
)
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
        # перечитываем, чтобы подтянуть relations (metrics, team_members)
        return await self.get(employee.id)

    async def list(
        self,
        *,
        team_id: UUID | None = None,
        risk_level: str | None = None,
        work_format: str | None = None,
        search: str | None = None,
        category: str | None = None,
    ) -> list[Employee]:
        return await self.employees.list(
            team_id=team_id,
            risk_level=risk_level,
            work_format=work_format,
            search=search,
            category=category,
        )

    async def get(self, employee_id: UUID) -> Employee:
        employee = await self.employees.get(employee_id)
        if employee is None:
            raise NotFoundError("employee not found")
        return employee

    async def update(
        self,
        employee_id: UUID,
        payload: EmployeeUpdate,
        *,
        changed_by: UUID,
    ) -> Employee:
        employee = await self.get(employee_id)
        before_snapshot = employee_to_dict(employee)
        values = payload.model_dump(exclude_unset=True)
        try:
            employee = await self.employees.update(employee, values)
            await record_change(
                self.session,
                entity_type=ENTITY_EMPLOYEE,
                entity_id=employee.id,
                employee_id=employee.id,
                action=ACTION_UPDATE,
                changed_by=changed_by,
                before=before_snapshot,
                after=employee_to_dict(employee),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise InvalidOperationError(
                "employee with this email or VK user id already exists"
            ) from exc
        return await self.get(employee.id)
