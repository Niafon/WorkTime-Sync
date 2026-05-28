from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.availability import team_overlap_summary
from app.models.employee_metric import EmployeeMetric
from app.models.team import Team
from app.models.team_member import TeamMember
from app.repositories.teams import TeamRepository
from app.schemas.team import TeamAvailabilityRankingItem, TeamMetricsResponse
from app.services.exceptions import NotFoundError
from app.services.team_availability import TeamAvailabilityService

_RISK_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}


class TeamMetricsService:
    """Агрегирует EmployeeMetric по составу команды."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.teams = TeamRepository(session)

    async def get(self, team_id: UUID) -> TeamMetricsResponse:
        team = await self.teams.get(team_id)
        if team is None:
            raise NotFoundError("team not found")

        result = await self.session.execute(
            select(EmployeeMetric)
            .join(TeamMember, TeamMember.employee_id == EmployeeMetric.employee_id)
            .where(TeamMember.team_id == team_id)
        )
        metrics = list(result.scalars().all())

        members_count_result = await self.session.execute(
            select(TeamMember.employee_id).where(TeamMember.team_id == team_id)
        )
        members_count = len(list(members_count_result.scalars().all()))

        if not metrics:
            return TeamMetricsResponse(
                team_id=team_id,
                members_count=members_count,
                attention_count=0,
                outdated_count=0,
                avg_actuality=None,
                avg_load=None,
                max_risk_level=None,
            )

        attention = sum(1 for m in metrics if m.risk_level in ("high", "critical"))
        outdated = sum(1 for m in metrics if m.days_since_update >= 60)
        avg_actuality = sum(m.actuality_score for m in metrics) / len(metrics)
        avg_load = sum(m.load_level for m in metrics) / len(metrics)
        max_risk = max(metrics, key=lambda m: _RISK_ORDER.get(m.risk_level, 0)).risk_level

        return TeamMetricsResponse(
            team_id=team_id,
            members_count=members_count,
            attention_count=attention,
            outdated_count=outdated,
            avg_actuality=round(avg_actuality, 3),
            avg_load=round(avg_load, 3),
            max_risk_level=max_risk,  # type: ignore[arg-type]
        )

    async def availability_ranking(
        self,
        *,
        window_days: int = 7,
        reference: datetime | None = None,
    ) -> list[TeamAvailabilityRankingItem]:
        """Рейтинг команд по пересечению доступности (Tteam, ТЗ §8).

        Возвращает список команд, отсортированный по `overlap_ratio` по возрастанию,
        чтобы команды с самым низким пересечением шли первыми.
        """
        anchor = reference or datetime.now(UTC)
        range_start = anchor.replace(hour=0, minute=0, second=0, microsecond=0)
        range_end = range_start + timedelta(days=max(1, window_days))

        teams_result = await self.session.execute(select(Team).order_by(Team.name.asc()))
        teams = list(teams_result.scalars().all())
        availability_service = TeamAvailabilityService(self.session)

        items: list[TeamAvailabilityRankingItem] = []
        for team in teams:
            employees, inputs = await availability_service._build_availability_inputs(  # noqa: SLF001
                team.id,
                range_start,
                range_end,
            )
            if not employees:
                items.append(
                    TeamAvailabilityRankingItem(
                        team_id=team.id,
                        name=team.name,
                        members_count=0,
                        overlap_ratio=0.0,
                        full_team_minutes=0.0,
                        majority_minutes=0.0,
                        total_window_minutes=(range_end - range_start).total_seconds() / 60,
                    )
                )
                continue
            from app.analytics.availability import (  # локальный импорт во избежание циклов
                calculate_employee_availability,
            )

            availability = [
                calculate_employee_availability(
                    employee_input,
                    range_start=range_start,
                    range_end=range_end,
                )
                for employee_input in inputs
            ]
            summary = team_overlap_summary(
                availability,
                range_start=range_start,
                range_end=range_end,
            )
            overlap_ratio = (
                summary.full_team_minutes / summary.total_window_minutes
                if summary.total_window_minutes > 0
                else 0.0
            )
            items.append(
                TeamAvailabilityRankingItem(
                    team_id=team.id,
                    name=team.name,
                    members_count=len(employees),
                    overlap_ratio=round(overlap_ratio, 4),
                    full_team_minutes=round(summary.full_team_minutes, 2),
                    majority_minutes=round(summary.majority_minutes, 2),
                    total_window_minutes=round(summary.total_window_minutes, 2),
                )
            )

        items.sort(key=lambda item: (item.overlap_ratio, item.name))
        return items
