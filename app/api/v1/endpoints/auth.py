from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentEmployeeDep, get_db_session
from app.schemas.auth import AuthTokenResponse, VKLoginResponse
from app.schemas.common import ErrorResponse
from app.schemas.employee import EmployeeResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]

error_responses: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
}


@router.get("/vk/login", response_model=VKLoginResponse)
async def vk_login(session: SessionDep) -> VKLoginResponse:
    return VKLoginResponse(authorization_url=AuthService(session).vk_authorization_url())


@router.get("/vk/callback", response_model=AuthTokenResponse, responses=error_responses)
async def vk_callback(
    session: SessionDep,
    code: str = Query(min_length=1),
) -> AuthTokenResponse:
    try:
        return await AuthService(session).authenticate_vk_code(code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/me", response_model=EmployeeResponse, responses=error_responses)
async def get_current_employee_profile(
    current_employee: CurrentEmployeeDep,
) -> EmployeeResponse:
    return EmployeeResponse.model_validate(current_employee)
