from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.availability import (
    EmployeeAvailabilityInput,
    TimeWindow,
    calculate_employee_availability,
    recommend_meeting_windows,
)
from app.models.employee import Employee
from app.models.work_schedule import WorkSchedule
from app.repositories.activity_events import ActivityEventRepository
from app.repositories.employees import EmployeeRepository
from app.repositories.schedule_exceptions import ScheduleExceptionRepository
from app.repositories.team_members import TeamMemberRepository
from app.repositories.teams import TeamRepository
from app.repositories.work_schedules import WorkScheduleRepository
from app.schemas.availability import (
    AvailabilityWindowResponse,
    EmployeeAvailabilityResponse,
    MeetingRecommendationRequest,
    MeetingRecommendationResponse,
    TeamAvailabilityResponse,
)
from app.services.exceptions import InvalidOperationError, NotFoundError

EXCLUDED_EXCEPTION_TYPES = {"vacation", "sick", "sick_leave"}


class TeamAvailabilityService:
    def __init__(self, session: AsyncSession) -> None:
        self.teams = TeamRepository(session)
        self.team_members = TeamMemberRepository(session)
        self.employees = EmployeeRepository(session)
        self.schedules = WorkScheduleRepository(session)
        self.exceptions = ScheduleExceptionRepository(session)
        self.events = ActivityEventRepository(session)

    async def get_availability(
        self,
        team_id: UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> TeamAvailabilityResponse:
        if range_start >= range_end:
            raise InvalidOperationError("range_start must be earlier than range_end")
        employees, inputs = await self._build_availability_inputs(team_id, range_start, range_end)
        availability_by_employee = {
            UUID(item.employee_id): item
            for item in (
                calculate_employee_availability(
                    employee_input,
                    range_start=range_start,
                    range_end=range_end,
                )
                for employee_input in inputs
            )
        }

        return TeamAvailabilityResponse(
            team_id=team_id,
            range_start=range_start,
            range_end=range_end,
            employees=[
                EmployeeAvailabilityResponse(
                    employee_id=employee.id,
                    timezone=employee.timezone,
                    available_windows=[
                        AvailabilityWindowResponse(
                            start_dt=window.start_dt,
                            end_dt=window.end_dt,
                        )
                        for window in availability_by_employee[employee.id].available_windows
                    ],
                )
                for employee in employees
            ],
        )

    async def recommend_meetings(
        self,
        team_id: UUID,
        payload: MeetingRecommendationRequest,
    ) -> list[MeetingRecommendationResponse]:
        if payload.start_dt >= payload.end_dt:
            raise InvalidOperationError("start_dt must be earlier than end_dt")
        employees, inputs = await self._build_availability_inputs(
            team_id,
            payload.start_dt,
            payload.end_dt,
        )
        availability = [
            calculate_employee_availability(
                employee_input,
                range_start=payload.start_dt,
                range_end=payload.end_dt,
            )
            for employee_input in inputs
        ]
        recommendations = recommend_meeting_windows(
            availability,
            range_start=payload.start_dt,
            range_end=payload.end_dt,
            duration_minutes=payload.duration_minutes,
        )
        employee_ids = {str(employee.id): employee.id for employee in employees}
        return [
            MeetingRecommendationResponse(
                start_dt=recommendation.start_dt,
                end_dt=recommendation.end_dt,
                available_employee_ids=[
                    employee_ids[employee_id]
                    for employee_id in recommendation.available_employee_ids
                ],
                unavailable_employee_ids=[
                    employee_ids[employee_id]
                    for employee_id in recommendation.unavailable_employee_ids
                ],
                score=recommendation.score,
            )
            for recommendation in recommendations
        ]

    async def _build_availability_inputs(
        self,
        team_id: UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> tuple[list[Employee], list[EmployeeAvailabilityInput]]:
        if await self.teams.get(team_id) is None:
            raise NotFoundError("team not found")

        employee_ids = await self.team_members.list_employee_ids_for_team(team_id)
        employees = await self.employees.list_by_ids(employee_ids)
        schedules = await self.schedules.list_active_for_employees(employee_ids)
        exceptions = await self.exceptions.list_for_employees_in_range(
            employee_ids,
            range_start,
            range_end,
        )
        events = await self.events.list_for_employees_in_range(employee_ids, range_start, range_end)

        schedules_by_employee = _group_by_employee(schedules)
        exceptions_by_employee = _group_by_employee(exceptions)
        events_by_employee = _group_by_employee(events)
        return employees, [
            EmployeeAvailabilityInput(
                employee_id=str(employee.id),
                schedule_windows=tuple(
                    window
                    for schedule in schedules_by_employee[employee.id]
                    for window in _schedule_windows_for_range(schedule, range_start, range_end)
                ),
                busy_windows=tuple(
                    [
                        *(
                            TimeWindow(item.start_dt, item.end_dt)
                            for item in exceptions_by_employee[employee.id]
                            if item.type in EXCLUDED_EXCEPTION_TYPES
                        ),
                        *(
                            TimeWindow(item.start_dt, item.end_dt)
                            for item in events_by_employee[employee.id]
                        ),
                    ]
                ),
            )
            for employee in employees
        ]


def _group_by_employee(items: Iterable[Any]) -> defaultdict[UUID, list[Any]]:
    grouped: defaultdict[UUID, list[Any]] = defaultdict(list)
    for item in items:
        grouped[item.employee_id].append(item)
    return grouped


def _schedule_windows_for_range(
    schedule: WorkSchedule,
    range_start: datetime,
    range_end: datetime,
) -> list[TimeWindow]:
    timezone = ZoneInfo(schedule.timezone)
    current_date = range_start.astimezone(timezone).date()
    end_date = range_end.astimezone(timezone).date()
    windows: list[TimeWindow] = []
    while current_date <= end_date:
        if current_date.weekday() in schedule.work_days:
            window = _local_window(current_date, schedule.start_time, schedule.end_time, timezone)
            if window.end_dt > range_start and window.start_dt < range_end:
                windows.append(window)
        current_date += timedelta(days=1)
    return windows


def _local_window(day: date, start_time: time, end_time: time, timezone: ZoneInfo) -> TimeWindow:
    return TimeWindow(
        start_dt=datetime.combine(day, start_time, tzinfo=timezone),
        end_dt=datetime.combine(day, end_time, tzinfo=timezone),
    )
