from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

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
