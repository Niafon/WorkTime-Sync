from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.dashboard import DashboardRepository
from app.schemas.dashboard import DashboardSummaryResponse

RISK_LEVELS = ("low", "medium", "high", "critical")


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.dashboard = DashboardRepository(session)

    async def get_summary(self) -> DashboardSummaryResponse:
        employees_by_risk_level = dict.fromkeys(RISK_LEVELS, 0)
        employees_by_risk_level.update(await self.dashboard.count_employees_by_risk_level())

        return DashboardSummaryResponse(
            total_employees=await self.dashboard.count_employees(),
            total_teams=await self.dashboard.count_teams(),
            employees_by_risk_level=employees_by_risk_level,
            overloaded_employees_count=await self.dashboard.count_overloaded_employees(),
            outdated_schedules_count=await self.dashboard.count_outdated_schedules(),
            outside_schedule_events_count=await self.dashboard.sum_outside_schedule_events(),
            last_calculation_at=await self.dashboard.last_calculation_at(),
        )
