from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentEmployeeDep, get_db_session
from app.schemas.common import ErrorResponse
from app.schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from app.schemas.schedule_exception import (
    ScheduleExceptionCreate,
    ScheduleExceptionResponse,
)
from app.schemas.work_schedule import WorkScheduleCreate, WorkScheduleResponse
from app.services.employees import EmployeeService
from app.services.exceptions import InvalidOperationError, NotFoundError
from app.services.schedule_exceptions import ScheduleExceptionService
from app.services.work_schedules import WorkScheduleService

router = APIRouter(prefix="/employees", tags=["employees"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]

error_responses: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
}


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses,
)
async def create_employee(
    payload: EmployeeCreate,
    session: SessionDep,
    _current_employee: CurrentEmployeeDep,
) -> EmployeeResponse:
    try:
        employee = await EmployeeService(session).create(payload)
    except InvalidOperationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EmployeeResponse.model_validate(employee)


@router.get("", response_model=list[EmployeeResponse])
async def list_employees(
    session: SessionDep,
) -> list[EmployeeResponse]:
    employees = await EmployeeService(session).list()
    return [EmployeeResponse.model_validate(employee) for employee in employees]


@router.get("/{employee_id}", response_model=EmployeeResponse, responses=error_responses)
async def get_employee(
    employee_id: UUID,
    session: SessionDep,
) -> EmployeeResponse:
    try:
        employee = await EmployeeService(session).get(employee_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return EmployeeResponse.model_validate(employee)


@router.patch("/{employee_id}", response_model=EmployeeResponse, responses=error_responses)
async def update_employee(
    employee_id: UUID,
    payload: EmployeeUpdate,
    session: SessionDep,
    _current_employee: CurrentEmployeeDep,
) -> EmployeeResponse:
    try:
        employee = await EmployeeService(session).update(employee_id, payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidOperationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return EmployeeResponse.model_validate(employee)


@router.post(
    "/{employee_id}/schedules",
    response_model=WorkScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses,
)
async def create_employee_schedule(
    employee_id: UUID,
    payload: WorkScheduleCreate,
    session: SessionDep,
    _current_employee: CurrentEmployeeDep,
) -> WorkScheduleResponse:
    try:
        schedule = await WorkScheduleService(session).create(employee_id, payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidOperationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return WorkScheduleResponse.model_validate(schedule)


@router.get(
    "/{employee_id}/schedules/active",
    response_model=WorkScheduleResponse,
    responses=error_responses,
)
async def get_active_employee_schedule(
    employee_id: UUID,
    session: SessionDep,
) -> WorkScheduleResponse:
    try:
        schedule = await WorkScheduleService(session).get_active(employee_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return WorkScheduleResponse.model_validate(schedule)


@router.post(
    "/{employee_id}/exceptions",
    response_model=ScheduleExceptionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses,
)
async def create_employee_exception(
    employee_id: UUID,
    payload: ScheduleExceptionCreate,
    session: SessionDep,
    _current_employee: CurrentEmployeeDep,
) -> ScheduleExceptionResponse:
    try:
        schedule_exception = await ScheduleExceptionService(session).create(employee_id, payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidOperationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ScheduleExceptionResponse.model_validate(schedule_exception)


@router.get(
    "/{employee_id}/exceptions",
    response_model=list[ScheduleExceptionResponse],
    responses=error_responses,
)
async def list_employee_exceptions(
    employee_id: UUID,
    session: SessionDep,
) -> list[ScheduleExceptionResponse]:
    try:
        schedule_exceptions = await ScheduleExceptionService(session).list_for_employee(employee_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [
        ScheduleExceptionResponse.model_validate(schedule_exception)
        for schedule_exception in schedule_exceptions
    ]
