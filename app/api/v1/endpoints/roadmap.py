from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CurrentEmployeeDep,
    get_db_session,
    require_roles,
    require_roles_or_self_employee,
)
from app.core.roles import MANAGEMENT_ROLES, EmployeeRole
from app.models.employee import Employee
from app.schemas.common import ErrorResponse
from app.schemas.roadmap import (
    RoadmapGenerateRequestBody,
    RoadmapGenerateResponse,
    RoadmapItemResponse,
    RoadmapItemUpdateRequest,
    RoadmapListResponse,
    RoadmapRecomputeResponse,
    RoadmapStatusUpdateRequest,
)
from app.services.exceptions import InvalidOperationError, NotFoundError
from app.services.roadmap import (
    RoadmapGenerateRequest,
    RoadmapItemUpdate,
    RoadmapListFilters,
    RoadmapService,
    RoadmapStatusUpdate,
)

router = APIRouter(tags=["roadmap"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]

error_responses: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
}


PlannerRoles = list(MANAGEMENT_ROLES)


def _filters(
    status_: list[str] | None,
    severity: list[str] | None,
    subject_type: str | None,
    team_id: UUID | None,
    employee_id: UUID | None,
    assigned_to_id: UUID | None,
    search: str | None,
    include_closed: bool,
    limit: int,
    offset: int,
) -> RoadmapListFilters:
    return RoadmapListFilters(
        statuses=status_ or None,
        severities=severity or None,
        subject_type=subject_type,
        team_id=team_id,
        employee_id=employee_id,
        assigned_to_id=assigned_to_id,
        search=search,
        include_closed=include_closed,
        limit=limit,
        offset=offset,
    )


def _to_list_response(result) -> RoadmapListResponse:
    return RoadmapListResponse(
        items=[RoadmapItemResponse.from_item(item) for item in result.items],
        total=result.total,
        counts_by_status=result.counts_by_status,
        counts_by_severity=result.counts_by_severity,
    )


@router.get("/roadmap", response_model=RoadmapListResponse)
async def list_roadmap(
    session: SessionDep,
    _current: CurrentEmployeeDep,
    status_: Annotated[list[str], Query(alias="status")] = [],
    severity: Annotated[list[str], Query()] = [],
    subject_type: str | None = None,
    team_id: UUID | None = None,
    employee_id: UUID | None = None,
    assigned_to_id: UUID | None = None,
    search: str | None = None,
    include_closed: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> RoadmapListResponse:
    filters = _filters(
        status_,
        severity,
        subject_type,
        team_id,
        employee_id,
        assigned_to_id,
        search,
        include_closed,
        limit,
        offset,
    )
    result = await RoadmapService(session).list(filters)
    return _to_list_response(result)


@router.get(
    "/roadmap/{item_id}",
    response_model=RoadmapItemResponse,
    responses=error_responses,
)
async def get_roadmap_item(
    item_id: UUID,
    session: SessionDep,
    _current: CurrentEmployeeDep,
) -> RoadmapItemResponse:
    try:
        item = await RoadmapService(session).get(item_id)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return RoadmapItemResponse.from_item(item)


@router.post(
    "/roadmap/generate",
    response_model=RoadmapGenerateResponse,
    responses=error_responses,
)
async def generate_roadmap(
    payload: RoadmapGenerateRequestBody,
    session: SessionDep,
    actor: Annotated[Employee, Depends(require_roles(*MANAGEMENT_ROLES))],
) -> RoadmapGenerateResponse:
    try:
        result = await RoadmapService(session).generate(
            RoadmapGenerateRequest(
                team_id=payload.team_id, employee_id=payload.employee_id
            ),
            actor,
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return RoadmapGenerateResponse(
        created=result.created,
        skipped=result.skipped,
        items=[RoadmapItemResponse.from_item(item) for item in result.items],
    )


@router.patch(
    "/roadmap/{item_id}",
    response_model=RoadmapItemResponse,
    responses=error_responses,
)
async def update_roadmap_item(
    item_id: UUID,
    payload: RoadmapItemUpdateRequest,
    session: SessionDep,
    actor: Annotated[Employee, Depends(require_roles(*MANAGEMENT_ROLES))],
) -> RoadmapItemResponse:
    try:
        item = await RoadmapService(session).update(
            item_id,
            RoadmapItemUpdate(
                notes=payload.notes,
                assigned_to_id=payload.assigned_to_id,
                due_at=payload.due_at,
            ),
            actor,
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return RoadmapItemResponse.from_item(item)


@router.patch(
    "/roadmap/{item_id}/status",
    response_model=RoadmapItemResponse,
    responses=error_responses,
)
async def update_roadmap_status(
    item_id: UUID,
    payload: RoadmapStatusUpdateRequest,
    session: SessionDep,
    actor: Annotated[Employee, Depends(require_roles(*MANAGEMENT_ROLES))],
) -> RoadmapItemResponse:
    try:
        item = await RoadmapService(session).update_status(
            item_id,
            RoadmapStatusUpdate(status=payload.status, notes=payload.notes),
            actor,
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except InvalidOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return RoadmapItemResponse.from_item(item)


@router.delete(
    "/roadmap/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_roadmap_item(
    item_id: UUID,
    session: SessionDep,
    actor: Annotated[Employee, Depends(require_roles(*MANAGEMENT_ROLES))],
) -> Response:
    try:
        await RoadmapService(session).delete(item_id, actor)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/roadmap/recompute",
    response_model=RoadmapRecomputeResponse,
)
async def recompute_roadmap_priorities(
    session: SessionDep,
    _admin: Annotated[Employee, Depends(require_roles(EmployeeRole.ADMIN))],
    team_id: UUID | None = None,
) -> RoadmapRecomputeResponse:
    updated = await RoadmapService(session).recompute_priorities(team_id=team_id)
    return RoadmapRecomputeResponse(updated=updated)


@router.get(
    "/teams/{team_id}/roadmap",
    response_model=RoadmapListResponse,
    responses=error_responses,
)
async def list_team_roadmap(
    team_id: UUID,
    session: SessionDep,
    _current: CurrentEmployeeDep,
    status_: Annotated[list[str], Query(alias="status")] = [],
    severity: Annotated[list[str], Query()] = [],
    include_closed: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> RoadmapListResponse:
    filters = RoadmapListFilters(
        statuses=status_ or None,
        severities=severity or None,
        include_closed=include_closed,
        limit=limit,
        offset=offset,
    )
    try:
        result = await RoadmapService(session).list_for_team(team_id, filters)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return _to_list_response(result)


@router.get(
    "/employees/{employee_id}/roadmap",
    response_model=RoadmapListResponse,
    responses=error_responses,
)
async def list_employee_roadmap(
    employee_id: UUID,
    session: SessionDep,
    _current: Annotated[
        Employee, Depends(require_roles_or_self_employee(*MANAGEMENT_ROLES))
    ],
    status_: Annotated[list[str], Query(alias="status")] = [],
    severity: Annotated[list[str], Query()] = [],
    include_closed: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> RoadmapListResponse:
    filters = RoadmapListFilters(
        statuses=status_ or None,
        severities=severity or None,
        include_closed=include_closed,
        limit=limit,
        offset=offset,
    )
    try:
        result = await RoadmapService(session).list_for_employee(
            employee_id, filters
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return _to_list_response(result)
