from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.common import ErrorResponse
from app.schemas.recommendation import RecommendationResponse
from app.services.exceptions import NotFoundError
from app.services.recommendations import RecommendationService

router = APIRouter(tags=["recommendations"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]

error_responses: dict[int | str, dict[str, Any]] = {
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
