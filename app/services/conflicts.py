from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.availability import (
    EmployeeAvailabilityInput,
    TimeWindow,
    calculate_employee_availability,
    recommend_meeting_windows,
)
from app.models.activity_event import ActivityEvent
from app.models.employee import Employee
from app.models.notification import NOTIFICATION_TYPE_RESCHEDULE_PROPOSAL, Notification
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.work_schedule import WorkSchedule
from app.repositories.activity_events import ActivityEventRepository
from app.repositories.employees import EmployeeRepository
from app.repositories.schedule_exceptions import ScheduleExceptionRepository
from app.repositories.team_members import TeamMemberRepository
from app.repositories.work_schedules import WorkScheduleRepository
from app.schemas.conflict import (
    AlternativeWindowResponse,
    ConflictEventResponse,
    ConflictListResponse,
    ProposeRescheduleRequest,
)
from app.services.exceptions import NotFoundError

EXCLUDED_EXCEPTION_TYPES = {"vacation", "sick", "sick_leave"}
ALTERNATIVE_RANGE_DAYS = 7
MAX_ALTERNATIVES = 3


class ConflictService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.events = ActivityEventRepository(session)
        self.employees = EmployeeRepository(session)
        self.team_members = TeamMemberRepository(session)
        self.schedules = WorkScheduleRepository(session)
        self.exceptions = ScheduleExceptionRepository(session)

    async def list_conflicts(
        self,
        *,
        team_id: UUID | None,
        employee_id: UUID | None,
        range_start: datetime | None,
        range_end: datetime | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> ConflictListResponse:
        employee_ids = await self._resolve_employee_ids(team_id, employee_id)
        events = await self.events.list_conflicts(
            employee_ids=employee_ids,
            range_start=range_start,
            range_end=range_end,
            search=search,
            limit=limit,
            offset=offset,
        )
        total = await self.events.count_conflicts(
            employee_ids=employee_ids,
            range_start=range_start,
            range_end=range_end,
            search=search,
        )
        if not events:
            return ConflictListResponse(items=[], total=total)

        unique_employee_ids = list({event.employee_id for event in events})
        employees = await self.employees.list_by_ids(unique_employee_ids)
        employee_by_id = {employee.id: employee for employee in employees}
        team_by_employee = await self._team_by_employee(unique_employee_ids)
        schedule_by_employee = {
            schedule.employee_id: schedule
            for schedule in await self.schedules.list_active_for_employees(unique_employee_ids)
        }

        items = [
            _build_conflict_response(
                event,
                employee=employee_by_id.get(event.employee_id),
                team=team_by_employee.get(event.employee_id),
                schedule=schedule_by_employee.get(event.employee_id),
            )
            for event in events
        ]
        return ConflictListResponse(items=items, total=total)

    async def list_alternatives(self, event_id: UUID) -> list[AlternativeWindowResponse]:
        event = await self.events.get(event_id)
        if event is None:
            raise NotFoundError("event not found")
        employee = await self.employees.get(event.employee_id)
        if employee is None:
            raise NotFoundError("employee not found")
        schedule = await self.schedules.get_active_for_employee(event.employee_id)
        if schedule is None:
            return []

        duration = event.end_dt - event.start_dt
        duration_minutes = max(int(duration.total_seconds() // 60), 1)
        range_start = event.start_dt - timedelta(days=ALTERNATIVE_RANGE_DAYS // 2)
        range_end = event.start_dt + timedelta(days=ALTERNATIVE_RANGE_DAYS // 2 + 1)

        schedule_windows = _schedule_windows_for_range(schedule, range_start, range_end)
        busy_events = await self.events.list_for_employees_in_range(
            [event.employee_id], range_start, range_end
        )
        busy_exceptions = await self.exceptions.list_for_employees_in_range(
            [event.employee_id], range_start, range_end
        )
        busy_windows = tuple(
            [
                *(
                    TimeWindow(other.start_dt, other.end_dt)
                    for other in busy_events
                    if other.id != event.id
                ),
                *(
                    TimeWindow(item.start_dt, item.end_dt)
                    for item in busy_exceptions
                    if item.type in EXCLUDED_EXCEPTION_TYPES
                ),
            ]
        )

        availability = calculate_employee_availability(
            EmployeeAvailabilityInput(
                employee_id=str(employee.id),
                schedule_windows=tuple(schedule_windows),
                busy_windows=busy_windows,
            ),
            range_start=range_start,
            range_end=range_end,
        )
        recommendations = recommend_meeting_windows(
            [availability],
            range_start=range_start,
            range_end=range_end,
            duration_minutes=duration_minutes,
            required_ids=frozenset({str(employee.id)}),
            max_recommendations=MAX_ALTERNATIVES,
        )

        tz = ZoneInfo(employee.timezone)
        return [
            AlternativeWindowResponse(
                start_dt=rec.start_dt,
                end_dt=rec.end_dt,
                local_start=rec.start_dt.astimezone(tz),
                local_end=rec.end_dt.astimezone(tz),
                reason="В рабочем графике, нет других встреч",
            )
            for rec in recommendations
        ]

    async def propose_reschedule(
        self,
        event_id: UUID,
        payload: ProposeRescheduleRequest,
        requester: Employee,
    ) -> None:
        event = await self.events.get(event_id)
        if event is None:
            raise NotFoundError("event not found")

        notification = Notification(
            recipient_id=event.employee_id,
            type=NOTIFICATION_TYPE_RESCHEDULE_PROPOSAL,
            title=f"Предложение перенести встречу «{event.title}»",
            body=(
                f"Перенести на {payload.alternative_start_dt:%d.%m %H:%M}"
                f"–{payload.alternative_end_dt:%H:%M}"
            ),
            payload={
                "event_id": str(event.id),
                "alternative_start": payload.alternative_start_dt.isoformat(),
                "alternative_end": payload.alternative_end_dt.isoformat(),
                "proposed_by": str(requester.id),
                "note": payload.note,
            },
        )
        self.session.add(notification)
        await self.session.commit()

    async def _resolve_employee_ids(
        self,
        team_id: UUID | None,
        employee_id: UUID | None,
    ) -> list[UUID] | None:
        if employee_id is not None:
            return [employee_id]
        if team_id is not None:
            return await self.team_members.list_employee_ids_for_team(team_id)
        return None

    async def _team_by_employee(
        self,
        employee_ids: list[UUID],
    ) -> dict[UUID, Team]:
        if not employee_ids:
            return {}
        result = await self.session.execute(
            select(TeamMember.employee_id, Team)
            .join(Team, Team.id == TeamMember.team_id)
            .where(TeamMember.employee_id.in_(employee_ids))
            .order_by(Team.name)
        )
        team_by_employee: dict[UUID, Team] = {}
        for employee_uuid, team in result.all():
            team_by_employee.setdefault(employee_uuid, team)
        return team_by_employee


def _build_conflict_response(
    event: ActivityEvent,
    *,
    employee: Employee | None,
    team: Team | None,
    schedule: WorkSchedule | None,
) -> ConflictEventResponse:
    return ConflictEventResponse(
        id=event.id,
        employee_id=event.employee_id,
        employee_full_name=employee.full_name if employee else "",
        team_id=team.id if team else None,
        team_name=team.name if team else None,
        title=event.title,
        start_dt=event.start_dt,
        end_dt=event.end_dt,
        timezone=event.timezone,
        event_type=event.event_type,
        source=event.source,
        schedule_start_time=schedule.start_time if schedule else None,
        schedule_end_time=schedule.end_time if schedule else None,
    )


def _schedule_windows_for_range(
    schedule: WorkSchedule,
    range_start: datetime,
    range_end: datetime,
) -> list[TimeWindow]:
    tz = ZoneInfo(schedule.timezone)
    current_date = range_start.astimezone(tz).date()
    end_date = range_end.astimezone(tz).date()
    windows: list[TimeWindow] = []
    while current_date <= end_date:
        if current_date.weekday() in schedule.work_days:
            start_dt = datetime.combine(current_date, schedule.start_time, tzinfo=tz)
            end_dt = datetime.combine(current_date, schedule.end_time, tzinfo=tz)
            if end_dt > range_start and start_dt < range_end:
                windows.append(TimeWindow(start_dt=start_dt, end_dt=end_dt))
        current_date += timedelta(days=1)
    return windows
