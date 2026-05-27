from collections import defaultdict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.metrics import MetricSnapshot
from app.analytics.recommendations import RecommendationContext, generate_recommendations
from app.models.employee import Employee
from app.models.employee_metric import EmployeeMetric
from app.models.work_schedule import WorkSchedule
from app.repositories.activity_events import ActivityEventRepository
from app.repositories.employee_metrics import EmployeeMetricRepository
from app.repositories.employees import EmployeeRepository
from app.repositories.roadmap_items import RoadmapItemRepository
from app.repositories.team_members import TeamMemberRepository
from app.repositories.teams import TeamRepository
from app.repositories.work_schedules import WorkScheduleRepository
from app.schemas.recommendation import RecommendationResponse
from app.services.exceptions import NotFoundError


class RecommendationService:
    def __init__(self, session: AsyncSession) -> None:
        self.employees = EmployeeRepository(session)
        self.teams = TeamRepository(session)
        self.team_members = TeamMemberRepository(session)
        self.metrics = EmployeeMetricRepository(session)
        self.events = ActivityEventRepository(session)
        self.schedules = WorkScheduleRepository(session)
        self.roadmap_items = RoadmapItemRepository(session)

    async def list_all(self) -> list[RecommendationResponse]:
        employees = await self.employees.list()
        return await self.recommend_for_employees(employees)

    async def list_for_employee(self, employee_id: UUID) -> list[RecommendationResponse]:
        employee = await self.employees.get(employee_id)
        if employee is None:
            raise NotFoundError("employee not found")
        return await self.recommend_for_employees([employee])

    async def list_for_team(self, team_id: UUID) -> list[RecommendationResponse]:
        if await self.teams.get(team_id) is None:
            raise NotFoundError("team not found")
        employee_ids = await self.team_members.list_employee_ids_for_team(team_id)
        employees = await self.employees.list_by_ids(employee_ids)
        return await self.recommend_for_employees(employees)

    async def recommend_for_employees(
        self,
        employees: list[Employee],
    ) -> list[RecommendationResponse]:
        employee_ids = [employee.id for employee in employees]
        metrics_by_employee = {
            metric.employee_id: metric
            for metric in await self.metrics.list_for_employees(employee_ids)
        }
        events_by_employee = defaultdict(list)
        for event in await self.events.list_for_employees(employee_ids):
            events_by_employee[event.employee_id].append(event)
        schedules_by_employee = _latest_schedules_by_employee(
            await self.schedules.list_active_for_employees(employee_ids)
        )

        recommendations: list[RecommendationResponse] = []
        for employee in employees:
            metric = metrics_by_employee.get(employee.id)
            schedule = schedules_by_employee.get(employee.id)
            context = RecommendationContext(
                employee_timezone=employee.timezone,
                metric=metric_snapshot_from_orm(metric),
                schedule_timezone=schedule.timezone if schedule is not None else None,
                event_timezones=tuple(event.timezone for event in events_by_employee[employee.id]),
            )
            recommendations.extend(
                RecommendationResponse(
                    code=recommendation.code,
                    reason=recommendation.reason,
                    severity=recommendation.severity,
                    action=recommendation.action,
                    subject_type="employee",
                    subject_id=employee.id,
                )
                for recommendation in generate_recommendations(context)
            )
        return await self._enrich_with_roadmap_status(recommendations)

    async def _enrich_with_roadmap_status(
        self,
        recommendations: list[RecommendationResponse],
    ) -> list[RecommendationResponse]:
        """Приклеивает status и roadmap_item_id из открытых RoadmapItem-ов."""
        if not recommendations:
            return recommendations
        subject_pairs = list({(r.subject_type, r.subject_id) for r in recommendations})
        open_items = await self.roadmap_items.list_open_for_subjects(subject_pairs)
        items_by_key: dict[tuple[str, UUID, str], object] = {}
        for item in open_items:
            key = (item.subject_type, item.subject_id, item.recommendation_code)
            existing = items_by_key.get(key)
            # Если несколько open для одного ключа — берём более свежий.
            if existing is None or item.created_at > existing.created_at:
                items_by_key[key] = item

        enriched: list[RecommendationResponse] = []
        for rec in recommendations:
            item = items_by_key.get((rec.subject_type, rec.subject_id, rec.code))
            enriched.append(
                rec.model_copy(
                    update={
                        "status": item.status if item is not None else None,
                        "roadmap_item_id": item.id if item is not None else None,
                    }
                )
            )
        return enriched


def _latest_schedules_by_employee(schedules: list[WorkSchedule]) -> dict[UUID, WorkSchedule]:
    latest_by_employee: dict[UUID, WorkSchedule] = {}
    for schedule in schedules:
        existing = latest_by_employee.get(schedule.employee_id)
        if existing is None or schedule.last_updated_at > existing.last_updated_at:
            latest_by_employee[schedule.employee_id] = schedule
    return latest_by_employee


def metric_snapshot_from_orm(metric: EmployeeMetric | None) -> MetricSnapshot | None:
    if metric is None:
        return None
    return MetricSnapshot(
        days_since_update=metric.days_since_update,
        actuality_score=metric.actuality_score,
        outside_events_count=metric.outside_events_count,
        total_events_count=metric.total_events_count,
        conflict_rate=metric.conflict_rate,
        load_level=metric.load_level,
        zone_factor=metric.zone_factor,
        hr_factor=metric.hr_factor,
        risk_score=metric.risk_score,
        risk_level=metric.risk_level,
    )
