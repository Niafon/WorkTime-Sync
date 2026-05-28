from datetime import datetime
from uuid import UUID

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.metrics import ACTUALITY_DECAY_DAYS
from app.models.employee_metric_snapshot import EmployeeMetricSnapshot
from app.models.team_member import TeamMember


class EmployeeMetricSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, snapshot: EmployeeMetricSnapshot) -> EmployeeMetricSnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def add_many(self, snapshots: list[EmployeeMetricSnapshot]) -> None:
        if not snapshots:
            return
        self.session.add_all(snapshots)
        await self.session.flush()

    async def avg_actuality_by_month(
        self,
        start_dt: datetime,
        end_dt: datetime,
    ) -> list[tuple[datetime, float]]:
        month = func.date_trunc("month", EmployeeMetricSnapshot.taken_at).label("month")
        result = await self.session.execute(
            select(month, func.avg(EmployeeMetricSnapshot.actuality_score))
            .where(
                EmployeeMetricSnapshot.taken_at >= start_dt,
                EmployeeMetricSnapshot.taken_at < end_dt,
            )
            .group_by(month)
            .order_by(month)
        )
        return [(row[0], float(row[1])) for row in result.all()]

    async def risk_distribution_by_month(
        self,
        start_dt: datetime,
        end_dt: datetime,
    ) -> list[tuple[datetime, str, int]]:
        month = func.date_trunc("month", EmployeeMetricSnapshot.taken_at).label("month")
        result = await self.session.execute(
            select(month, EmployeeMetricSnapshot.risk_level, func.count())
            .where(
                EmployeeMetricSnapshot.taken_at >= start_dt,
                EmployeeMetricSnapshot.taken_at < end_dt,
            )
            .group_by(month, EmployeeMetricSnapshot.risk_level)
            .order_by(month)
        )
        return [(row[0], row[1], int(row[2])) for row in result.all()]

    async def team_metrics_history_by_month(
        self,
        team_id: UUID,
        start_dt: datetime,
        end_dt: datetime,
    ) -> list[tuple[datetime, float, float, int]]:
        """Возвращает [(month, avg_ai, avg_ri, attention_count), ...] для команды.

        attention_count — число снимков с risk_level ∈ {high, critical} в месяце.
        Соответствие сотрудник↔команда — через team_members.
        """
        month = func.date_trunc("month", EmployeeMetricSnapshot.taken_at).label("month")
        attention_sum = func.coalesce(
            func.sum(
                func.cast(
                    EmployeeMetricSnapshot.risk_level.in_(("high", "critical")),
                    Integer,
                )
            ),
            0,
        )
        result = await self.session.execute(
            select(
                month,
                func.coalesce(func.avg(EmployeeMetricSnapshot.actuality_score), 0.0),
                func.coalesce(func.avg(EmployeeMetricSnapshot.risk_score), 0.0),
                attention_sum,
            )
            .join(
                TeamMember,
                TeamMember.employee_id == EmployeeMetricSnapshot.employee_id,
            )
            .where(
                TeamMember.team_id == team_id,
                EmployeeMetricSnapshot.taken_at >= start_dt,
                EmployeeMetricSnapshot.taken_at < end_dt,
            )
            .group_by(month)
            .order_by(month)
        )
        return [
            (row[0], float(row[1]), float(row[2]), int(row[3]))
            for row in result.all()
        ]

    async def averages_in_window(
        self,
        start_dt: datetime,
        end_dt: datetime,
    ) -> tuple[float, float, int]:
        """Возвращает (avg_actuality, avg_conflict_rate, outdated_count) в окне."""
        result = await self.session.execute(
            select(
                func.coalesce(func.avg(EmployeeMetricSnapshot.actuality_score), 0.0),
                func.coalesce(func.avg(EmployeeMetricSnapshot.conflict_rate), 0.0),
                func.coalesce(
                    func.sum(
                        func.cast(
                            EmployeeMetricSnapshot.days_since_update >= ACTUALITY_DECAY_DAYS,
                            Integer,
                        )
                    ),
                    0,
                ),
            ).where(
                EmployeeMetricSnapshot.taken_at >= start_dt,
                EmployeeMetricSnapshot.taken_at < end_dt,
            )
        )
        row = result.one()
        return float(row[0]), float(row[1]), int(row[2])
