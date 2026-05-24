from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.dashboard import DashboardSummaryResponse
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(session: SessionDep) -> DashboardSummaryResponse:
    return await DashboardService(session).get_summary()
