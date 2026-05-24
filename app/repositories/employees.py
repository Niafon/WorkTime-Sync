from __future__ import annotations

import builtins
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee


class EmployeeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, employee: Employee) -> Employee:
        self.session.add(employee)
        await self.session.flush()
        await self.session.refresh(employee)
        return employee

    async def list(self) -> list[Employee]:
        result = await self.session.execute(select(Employee).order_by(Employee.created_at.desc()))
        return list(result.scalars().all())

    async def get(self, employee_id: UUID) -> Employee | None:
        return await self.session.get(Employee, employee_id)

    async def get_by_vk_user_id(self, vk_user_id: str) -> Employee | None:
        result = await self.session.execute(
            select(Employee).where(Employee.vk_user_id == vk_user_id)
        )
        return result.scalar_one_or_none()

    async def list_by_ids(self, employee_ids: builtins.list[UUID]) -> builtins.list[Employee]:
        if not employee_ids:
            return []
        result = await self.session.execute(
            select(Employee).where(Employee.id.in_(employee_ids)).order_by(Employee.full_name)
        )
        return list(result.scalars().all())

    async def update(self, employee: Employee, values: dict[str, object]) -> Employee:
        for field, value in values.items():
            setattr(employee, field, value)
        await self.session.flush()
        await self.session.refresh(employee)
        return employee
