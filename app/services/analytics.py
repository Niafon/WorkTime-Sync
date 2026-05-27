from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee_metric import EmployeeMetric
from app.models.team import Team
from app.models.team_member import TeamMember
from app.repositories.employee_metric_snapshots import EmployeeMetricSnapshotRepository
from app.schemas.analytics import (
    ActualityHistoryPoint,
    RiskDistributionPoint,
    SummaryDeltasResponse,
    TeamMetricsHistoryPoint,
    TeamRatingItem,
)

RISK_LEVELS: tuple[str, ...] = ("low", "medium", "high", "critical")
ATTENTION_RISK_LEVELS = frozenset({"high", "critical"})
PERIOD_DAYS: dict[str, int] = {"month": 30, "week": 7}


class AnalyticsService:
    """Аналитика для роли Аналитик (ТЗ §11, §14).

    Использует employee_metric_snapshots как источник timeseries.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.snapshots = EmployeeMetricSnapshotRepository(session)

    async def actuality_history(self, months: int) -> list[ActualityHistoryPoint]:
        start_dt, end_dt = _months_window(months)
        rows = await self.snapshots.avg_actuality_by_month(start_dt, end_dt)
        return [
            ActualityHistoryPoint(month=_month_label(month), value=round(value, 3))
            for month, value in rows
        ]

    async def risk_distribution_history(self, months: int) -> list[RiskDistributionPoint]:
        start_dt, end_dt = _months_window(months)
        rows = await self.snapshots.risk_distribution_by_month(start_dt, end_dt)
        bucket: dict[str, dict[str, int]] = {}
        for month, risk_level, count in rows:
            key = _month_label(month)
            bucket.setdefault(key, dict.fromkeys(RISK_LEVELS, 0))
            if risk_level in bucket[key]:
                bucket[key][risk_level] = count
        return [
            RiskDistributionPoint(month=key, **counts)
            for key, counts in sorted(bucket.items())
        ]

    async def team_rating(self, limit: int) -> list[TeamRatingItem]:
        result = await self.session.execute(
            select(
                Team.id,
                Team.name,
                TeamMember.employee_id,
                EmployeeMetric.actuality_score,
                EmployeeMetric.risk_score,
                EmployeeMetric.risk_level,
            )
            .join(TeamMember, TeamMember.team_id == Team.id)
            .outerjoin(EmployeeMetric, EmployeeMetric.employee_id == TeamMember.employee_id)
        )
        teams_data: dict[tuple, dict] = {}
        for team_id, name, _employee_id, actuality, risk_score, risk_level in result.all():
            key = (team_id, name)
            entry = teams_data.setdefault(
                key,
                {
                    "members_count": 0,
                    "actuality_sum": 0.0,
                    "actuality_n": 0,
                    "risk_sum": 0.0,
                    "risk_n": 0,
                    "attention_count": 0,
                },
            )
            entry["members_count"] += 1
            if actuality is not None:
                entry["actuality_sum"] += actuality
                entry["actuality_n"] += 1
            if risk_score is not None:
                entry["risk_sum"] += risk_score
                entry["risk_n"] += 1
            if risk_level in ATTENTION_RISK_LEVELS:
                entry["attention_count"] += 1

        items = [
            TeamRatingItem(
                team_id=team_id,
                name=name,
                members_count=entry["members_count"],
                avg_actuality=(
                    round(entry["actuality_sum"] / entry["actuality_n"], 3)
                    if entry["actuality_n"] > 0
                    else 0.0
                ),
                avg_risk_score=(
                    round(entry["risk_sum"] / entry["risk_n"], 3)
                    if entry["risk_n"] > 0
                    else 0.0
                ),
                attention_count=entry["attention_count"],
            )
            for (team_id, name), entry in teams_data.items()
        ]
        items.sort(key=lambda item: (item.avg_actuality, -item.avg_risk_score, item.name))
        return items[:limit]

    async def summary_deltas(
        self,
        period: Literal["month", "week"],
    ) -> SummaryDeltasResponse:
        days = PERIOD_DAYS[period]
        now = datetime.now(UTC)
        current_start = now - timedelta(days=days)
        previous_start = current_start - timedelta(days=days)

        current_ai, current_ci, current_outdated = await self.snapshots.averages_in_window(
            current_start, now
        )
        previous_ai, previous_ci, previous_outdated = await self.snapshots.averages_in_window(
            previous_start, current_start
        )

        return SummaryDeltasResponse(
            period=period,
            ai_delta=round(current_ai - previous_ai, 3),
            ci_delta=round(current_ci - previous_ci, 3),
            outdated_schedules_delta=current_outdated - previous_outdated,
        )

    async def team_metrics_history(
        self,
        team_id: UUID,
        months: int,
    ) -> list[TeamMetricsHistoryPoint]:
        """Динамика метрик команды по месяцам: avg Ai, avg Ri, attention_count."""
        start_dt, end_dt = _months_window(months)
        rows = await self.snapshots.team_metrics_history_by_month(team_id, start_dt, end_dt)
        return [
            TeamMetricsHistoryPoint(
                month=_month_label(month),
                avg_actuality=round(avg_ai, 3),
                avg_risk_score=round(avg_ri, 3),
                attention_count=attention,
            )
            for month, avg_ai, avg_ri, attention in rows
        ]


def _months_window(months: int) -> tuple[datetime, datetime]:
    end_dt = datetime.now(UTC)
    start_dt = end_dt - timedelta(days=max(1, months) * 31)
    return start_dt, end_dt


def _month_label(value: datetime) -> str:
    return value.strftime("%Y-%m")
