from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentEmployeeDep, get_db_session
from app.schemas.common import ErrorResponse
from app.schemas.conflict import (
    AlternativeWindowResponse,
    ConflictListResponse,
    ProposeRescheduleRequest,
)
from app.services.conflicts import ConflictService
from app.services.exceptions import NotFoundError

router = APIRouter(prefix="/conflicts", tags=["conflicts"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]

error_responses: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
}


@router.get("", response_model=ConflictListResponse)
async def list_conflicts(
    session: SessionDep,
    team_id: UUID | None = None,
    employee_id: UUID | None = None,
    range_start: datetime | None = None,
    range_end: datetime | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ConflictListResponse:
    return await ConflictService(session).list_conflicts(
        team_id=team_id,
        employee_id=employee_id,
        range_start=range_start,
        range_end=range_end,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{event_id}/alternatives",
    response_model=list[AlternativeWindowResponse],
    responses=error_responses,
)
async def get_alternatives(
    event_id: UUID,
    session: SessionDep,
) -> list[AlternativeWindowResponse]:
    try:
        return await ConflictService(session).list_alternatives(event_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/{event_id}/propose-reschedule",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses,
)
async def propose_reschedule(
    event_id: UUID,
    payload: ProposeRescheduleRequest,
    session: SessionDep,
    current: CurrentEmployeeDep,
) -> Response:
    try:
        await ConflictService(session).propose_reschedule(event_id, payload, current)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
