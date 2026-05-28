from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import EmployeeRole
from app.core.security import decode_access_token
from app.db.session import get_async_session
from app.models.employee import Employee
from app.repositories.employees import EmployeeRepository


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_session():
        yield session


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/vk/callback")
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]


async def get_current_employee(
    session: SessionDep,
    token: TokenDep,
) -> Employee:
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    employee = await EmployeeRepository(session).get(payload.employee_id)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="employee not found for token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return employee


CurrentEmployeeDep = Annotated[Employee, Depends(get_current_employee)]


def require_roles(*allowed: EmployeeRole) -> Callable[..., Awaitable[Employee]]:
    """Запрещает доступ, если current.role не входит в allowed."""

    allowed_values = frozenset(role.value for role in allowed)

    async def _checker(current: CurrentEmployeeDep) -> Employee:
        if current.role not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="insufficient permissions",
            )
        return current

    return _checker


def require_roles_or_self_employee(
    *allowed: EmployeeRole,
) -> Callable[..., Awaitable[Employee]]:
    """Разрешает доступ, если current.role в allowed ИЛИ current.id == path['employee_id']."""

    allowed_values = frozenset(role.value for role in allowed)

    async def _checker(employee_id: UUID, current: CurrentEmployeeDep) -> Employee:
        if current.role in allowed_values:
            return current
        if current.id == employee_id:
            return current
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="insufficient permissions",
        )

    return _checker
