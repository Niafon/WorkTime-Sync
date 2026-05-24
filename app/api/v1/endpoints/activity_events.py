from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentEmployeeDep, get_db_session
from app.importers.activity_events import (
    ActivityEventImportValidationError,
    parse_csv_activity_events,
    parse_json_activity_events,
)
from app.schemas.activity_event import (
    ActivityEventCreate,
    ActivityEventImportResult,
    ActivityEventResponse,
)
from app.schemas.common import ErrorResponse
from app.services.activity_events import ActivityEventService
from app.services.exceptions import InvalidOperationError, NotFoundError

router = APIRouter(tags=["activity events"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CsvFileDep = Annotated[UploadFile, File(...)]

error_responses: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
}


@router.post(
    "/import/events/csv",
    response_model=ActivityEventImportResult,
    responses=error_responses,
)
async def import_activity_events_csv(
    session: SessionDep,
    file: CsvFileDep,
    _current_employee: CurrentEmployeeDep,
) -> ActivityEventImportResult:
    content = (await file.read()).decode("utf-8-sig")
    try:
        events = parse_csv_activity_events(content)
        return await ActivityEventService(session).import_events(events)
    except ActivityEventImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.errors) from exc
    except InvalidOperationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/import/events/json",
    response_model=ActivityEventImportResult,
    responses=error_responses,
)
async def import_activity_events_json(
    payload: list[dict[str, object]],
    session: SessionDep,
    _current_employee: CurrentEmployeeDep,
) -> ActivityEventImportResult:
    try:
        events = parse_json_activity_events(payload)
        return await ActivityEventService(session).import_events(events)
    except ActivityEventImportValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.errors) from exc
    except InvalidOperationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/events/manual",
    response_model=ActivityEventResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses,
)
async def create_manual_activity_event(
    payload: ActivityEventCreate,
    session: SessionDep,
    _current_employee: CurrentEmployeeDep,
) -> ActivityEventResponse:
    try:
        event = await ActivityEventService(session).create_manual(payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidOperationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ActivityEventResponse.model_validate(event)


@router.get(
    "/employees/{employee_id}/events",
    response_model=list[ActivityEventResponse],
    responses=error_responses,
)
async def list_employee_activity_events(
    employee_id: UUID,
    session: SessionDep,
) -> list[ActivityEventResponse]:
    try:
        events = await ActivityEventService(session).list_for_employee(employee_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [ActivityEventResponse.model_validate(event) for event in events]
