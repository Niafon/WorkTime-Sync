from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_roles
from app.core.roles import MANAGEMENT_ROLES
from app.models.employee import Employee
from app.schemas.common import ErrorResponse
from app.schemas.recommendation import (
    RecommendationBulkStatusRequest,
    RecommendationBulkStatusResponse,
    RecommendationResponse,
    RecommendationStatusUpdateRequest,
)
from app.services.exceptions import InvalidOperationError, NotFoundError
from app.services.recommendations import RecommendationService
from app.services.roadmap import RoadmapService

router = APIRouter(tags=["recommendations"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]

error_responses: dict[int | str, dict[str, Any]] = {
    status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
}


@router.get("/recommendations", response_model=list[RecommendationResponse])
async def list_recommendations(session: SessionDep) -> list[RecommendationResponse]:
    return await RecommendationService(session).list_all()


@router.get(
    "/employees/{employee_id}/recommendations",
    response_model=list[RecommendationResponse],
    responses=error_responses,
)
async def list_employee_recommendations(
    employee_id: UUID,
    session: SessionDep,
) -> list[RecommendationResponse]:
    try:
        return await RecommendationService(session).list_for_employee(employee_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/teams/{team_id}/recommendations",
    response_model=list[RecommendationResponse],
    responses=error_responses,
)
async def list_team_recommendations(
    team_id: UUID,
    session: SessionDep,
) -> list[RecommendationResponse]:
    try:
        return await RecommendationService(session).list_for_team(team_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch(
    "/recommendations/{code}/{subject_type}/{subject_id}/status",
    response_model=RecommendationResponse,
    responses=error_responses,
)
async def update_recommendation_status(
    code: str,
    subject_type: Literal["employee", "team"],
    subject_id: UUID,
    payload: RecommendationStatusUpdateRequest,
    session: SessionDep,
    actor: Annotated[Employee, Depends(require_roles(*MANAGEMENT_ROLES))],
) -> RecommendationResponse:
    """Сохраняет действие пользователя над рекомендацией.

    Авто-промоутит рекомендацию в RoadmapItem (если ещё нет открытого) и сразу
    транзитит его статус через state-machine RoadmapService.
    """
    roadmap_service = RoadmapService(session)
    try:
        await roadmap_service.apply_recommendation_status(
            code=code,
            subject_type=subject_type,
            subject_id=subject_id,
            target_status=payload.status,
            actor=actor,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidOperationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    enriched = await _reload_recommendation(
        session,
        code=code,
        subject_type=subject_type,
        subject_id=subject_id,
    )
    if enriched is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="recommendation not found after status update",
        )
    return enriched


@router.post(
    "/recommendations/bulk-status",
    response_model=RecommendationBulkStatusResponse,
    responses=error_responses,
)
async def bulk_update_recommendation_status(
    payload: RecommendationBulkStatusRequest,
    session: SessionDep,
    actor: Annotated[Employee, Depends(require_roles(*MANAGEMENT_ROLES))],
) -> RecommendationBulkStatusResponse:
    """Массовое применение статуса к рекомендациям, отфильтрованным по severity/subject_type."""
    recommendation_service = RecommendationService(session)
    roadmap_service = RoadmapService(session)

    recommendations = await recommendation_service.list_all()
    updated = 0
    skipped = 0
    for rec in recommendations:
        if payload.severity is not None and rec.severity != payload.severity:
            continue
        if payload.subject_type is not None and rec.subject_type != payload.subject_type:
            continue
        try:
            await roadmap_service.apply_recommendation_status(
                code=rec.code,
                subject_type=rec.subject_type,
                subject_id=rec.subject_id,
                target_status=payload.status,
                actor=actor,
            )
            updated += 1
        except (InvalidOperationError, NotFoundError):
            skipped += 1
    return RecommendationBulkStatusResponse(updated=updated, skipped=skipped)


async def _reload_recommendation(
    session: AsyncSession,
    *,
    code: str,
    subject_type: str,
    subject_id: UUID,
) -> RecommendationResponse | None:
    """Перевычисляет рекомендации после PATCH и возвращает одну по коду+subject."""
    service = RecommendationService(session)
    try:
        if subject_type == "employee":
            recs = await service.list_for_employee(subject_id)
        elif subject_type == "team":
            recs = await service.list_for_team(subject_id)
        else:
            return None
    except NotFoundError:
        return None
    for rec in recs:
        if rec.code == code and rec.subject_id == subject_id:
            return rec
    return None
