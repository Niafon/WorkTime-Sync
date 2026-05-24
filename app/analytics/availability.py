from dataclasses import dataclass
from datetime import datetime, time, timedelta


@dataclass(frozen=True, slots=True)
class WorkScheduleWindow:
    work_days: tuple[int, ...]
    start_time: time
    end_time: time


@dataclass(frozen=True, slots=True)
class TimeWindow:
    start_dt: datetime
    end_dt: datetime


@dataclass(frozen=True, slots=True)
class EmployeeAvailabilityInput:
    employee_id: str
    schedule_windows: tuple[TimeWindow, ...]
    busy_windows: tuple[TimeWindow, ...]


@dataclass(frozen=True, slots=True)
class EmployeeAvailability:
    employee_id: str
    available_windows: tuple[TimeWindow, ...]


@dataclass(frozen=True, slots=True)
class MeetingRecommendation:
    start_dt: datetime
    end_dt: datetime
    available_employee_ids: tuple[str, ...]
    unavailable_employee_ids: tuple[str, ...]
    score: float


MEETING_SLOT_MINUTES = 30
MAX_MEETING_RECOMMENDATIONS = 3


def work_hours(schedule: WorkScheduleWindow) -> float:
    start_seconds = _seconds_since_midnight(schedule.start_time)
    end_seconds = _seconds_since_midnight(schedule.end_time)
    if end_seconds <= start_seconds:
        return 0.0
    return (end_seconds - start_seconds) / 3600


def is_event_outside_schedule(
    *,
    start_dt: datetime,
    end_dt: datetime,
    schedule: WorkScheduleWindow,
) -> bool:
    if start_dt >= end_dt:
        return True
    if start_dt.date() != end_dt.date():
        return True
    if start_dt.weekday() not in schedule.work_days:
        return True
    return start_dt.time() < schedule.start_time or end_dt.time() > schedule.end_time


def calculate_employee_availability(
    employee: EmployeeAvailabilityInput,
    *,
    range_start: datetime,
    range_end: datetime,
) -> EmployeeAvailability:
    free_windows: list[TimeWindow] = []
    for schedule_window in employee.schedule_windows:
        clipped = _clip_window(schedule_window, range_start, range_end)
        if clipped is None:
            continue
        free_windows.extend(_subtract_windows(clipped, employee.busy_windows))
    return EmployeeAvailability(
        employee_id=employee.employee_id,
        available_windows=tuple(_merge_windows(free_windows)),
    )


def recommend_meeting_windows(
    availability: list[EmployeeAvailability],
    *,
    range_start: datetime,
    range_end: datetime,
    duration_minutes: int,
    max_recommendations: int = MAX_MEETING_RECOMMENDATIONS,
) -> list[MeetingRecommendation]:
    if duration_minutes <= 0 or range_start >= range_end or not availability:
        return []

    duration = timedelta(minutes=duration_minutes)
    slot_step = timedelta(minutes=MEETING_SLOT_MINUTES)
    recommendations: list[MeetingRecommendation] = []
    current = range_start
    while current + duration <= range_end:
        candidate = TimeWindow(start_dt=current, end_dt=current + duration)
        available_ids = tuple(
            employee.employee_id
            for employee in availability
            if any(_contains(window, candidate) for window in employee.available_windows)
        )
        if available_ids:
            available_id_set = set(available_ids)
            unavailable_ids = tuple(
                employee.employee_id
                for employee in availability
                if employee.employee_id not in available_id_set
            )
            recommendations.append(
                MeetingRecommendation(
                    start_dt=candidate.start_dt,
                    end_dt=candidate.end_dt,
                    available_employee_ids=available_ids,
                    unavailable_employee_ids=unavailable_ids,
                    score=len(available_ids) / len(availability),
                )
            )
        current += slot_step

    recommendations.sort(key=lambda item: (-item.score, item.start_dt, item.end_dt))
    return recommendations[:max_recommendations]


def _seconds_since_midnight(value: time) -> int:
    return value.hour * 3600 + value.minute * 60 + value.second


def _clip_window(
    window: TimeWindow,
    range_start: datetime,
    range_end: datetime,
) -> TimeWindow | None:
    start_dt = max(window.start_dt, range_start)
    end_dt = min(window.end_dt, range_end)
    if start_dt >= end_dt:
        return None
    return TimeWindow(start_dt=start_dt, end_dt=end_dt)


def _subtract_windows(
    base_window: TimeWindow,
    blockers: tuple[TimeWindow, ...],
) -> list[TimeWindow]:
    free_windows = [base_window]
    overlapping_blockers = _merge_windows(
        [
            clipped
            for blocker in blockers
            if (clipped := _clip_window(blocker, base_window.start_dt, base_window.end_dt))
            is not None
        ]
    )
    for blocker in overlapping_blockers:
        next_windows: list[TimeWindow] = []
        for free_window in free_windows:
            next_windows.extend(_subtract_one(free_window, blocker))
        free_windows = next_windows
    return free_windows


def _subtract_one(base_window: TimeWindow, blocker: TimeWindow) -> list[TimeWindow]:
    if blocker.end_dt <= base_window.start_dt or blocker.start_dt >= base_window.end_dt:
        return [base_window]

    windows: list[TimeWindow] = []
    if blocker.start_dt > base_window.start_dt:
        windows.append(TimeWindow(start_dt=base_window.start_dt, end_dt=blocker.start_dt))
    if blocker.end_dt < base_window.end_dt:
        windows.append(TimeWindow(start_dt=blocker.end_dt, end_dt=base_window.end_dt))
    return windows


def _merge_windows(windows: list[TimeWindow]) -> list[TimeWindow]:
    if not windows:
        return []
    ordered = sorted(windows, key=lambda window: (window.start_dt, window.end_dt))
    merged = [ordered[0]]
    for window in ordered[1:]:
        previous = merged[-1]
        if window.start_dt <= previous.end_dt:
            merged[-1] = TimeWindow(previous.start_dt, max(previous.end_dt, window.end_dt))
        else:
            merged.append(window)
    return merged


def _contains(container: TimeWindow, candidate: TimeWindow) -> bool:
    return container.start_dt <= candidate.start_dt and container.end_dt >= candidate.end_dt
