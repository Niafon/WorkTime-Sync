from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee_metric import EmployeeMetric

# Поля, которые перезаписываются при ON CONFLICT — всё кроме id (PK) и employee_id (ключ конфликта).
_METRIC_UPDATABLE_FIELDS = (
    "calculated_at",
    "days_since_update",
    "actuality_score",
    "outside_events_count",
    "total_events_count",
    "conflict_rate",
    "load_level",
    "zone_factor",
    "hr_factor",
    "risk_score",
    "risk_level",
)


class EmployeeMetricRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_employee(self, employee_id: UUID) -> EmployeeMetric | None:
        result = await self.session.execute(
            select(EmployeeMetric).where(EmployeeMetric.employee_id == employee_id)
        )
        return result.scalar_one_or_none()

    async def list_for_employees(self, employee_ids: list[UUID]) -> list[EmployeeMetric]:
        if not employee_ids:
            return []
        result = await self.session.execute(
            select(EmployeeMetric).where(EmployeeMetric.employee_id.in_(employee_ids))
        )
        return list(result.scalars().all())

    async def upsert(self, metric: EmployeeMetric) -> EmployeeMetric:
        """Atomic upsert через PostgreSQL `INSERT ... ON CONFLICT DO UPDATE`.

        Безопасно для параллельных вызовов (например двух одновременных
        `recompute_for_employee_id`): уникальный индекс на `employee_id`
        гарантирует, что в БД останется одна строка, и оба клиента увидят
        самые свежие значения после своей операции.
        """
        values = {
            "employee_id": metric.employee_id,
            **{field: getattr(metric, field) for field in _METRIC_UPDATABLE_FIELDS},
        }
        stmt = (
            pg_insert(EmployeeMetric)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[EmployeeMetric.employee_id],
                set_={field: values[field] for field in _METRIC_UPDATABLE_FIELDS},
            )
            .returning(EmployeeMetric)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one()
