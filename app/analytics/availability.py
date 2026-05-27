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
    required_available_ids: tuple[str, ...]
    required_missing_ids: tuple[str, ...]
    optional_available_ids: tuple[str, ...]
    optional_missing_ids: tuple[str, ...]
    overloaded_employee_ids: tuple[str, ...]
    score: float


MEETING_SLOT_MINUTES = 30
MAX_MEETING_RECOMMENDATIONS = 3
DEFAULT_LOAD_THRESHOLD = 0.8

SCORE_REQUIRED_WEIGHT = 0.6
SCORE_OPTIONAL_WEIGHT = 0.3
SCORE_OVERLOAD_PENALTY_WEIGHT = 0.1


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
    required_ids: frozenset[str] = frozenset(),
    optional_ids: frozenset[str] = frozenset(),
    overloaded_ids: frozenset[str] = frozenset(),
    max_recommendations: int = MAX_MEETING_RECOMMENDATIONS,
) -> list[MeetingRecommendation]:
    if duration_minutes <= 0 or range_start >= range_end or not availability:
        return []

    effective_required = required_ids or frozenset(
        employee.employee_id for employee in availability
    )

    duration = timedelta(minutes=duration_minutes)
    slot_step = timedelta(minutes=MEETING_SLOT_MINUTES)
    overloaded_in_team = tuple(
        sorted(
            employee.employee_id
            for employee in availability
            if employee.employee_id in overloaded_ids
        )
    )
    recommendations: list[MeetingRecommendation] = []
    current = range_start
    while current + duration <= range_end:
        candidate = TimeWindow(start_dt=current, end_dt=current + duration)
        available_employee_ids = {
            employee.employee_id
            for employee in availability
            if employee.employee_id not in overloaded_ids
            and any(_contains(window, candidate) for window in employee.available_windows)
        }
        required_available = tuple(
            sorted(eid for eid in effective_required if eid in available_employee_ids)
        )
        required_missing = tuple(
            sorted(eid for eid in effective_required if eid not in available_employee_ids)
        )
        if required_missing:
            current += slot_step
            continue
        optional_available = tuple(
            sorted(eid for eid in optional_ids if eid in available_employee_ids)
        )
        optional_missing = tuple(
            sorted(eid for eid in optional_ids if eid not in available_employee_ids)
        )
        score = _score_candidate(
            required_available_count=len(required_available),
            required_total=len(effective_required),
            optional_available_count=len(optional_available),
            optional_total=len(optional_ids),
            overloaded_in_team_count=len(overloaded_in_team),
            team_size=len(availability),
        )
        recommendations.append(
            MeetingRecommendation(
                start_dt=candidate.start_dt,
                end_dt=candidate.end_dt,
                required_available_ids=required_available,
                required_missing_ids=required_missing,
                optional_available_ids=optional_available,
                optional_missing_ids=optional_missing,
                overloaded_employee_ids=overloaded_in_team,
                score=score,
            )
        )
        current += slot_step

    recommendations.sort(key=lambda item: (-item.score, item.start_dt, item.end_dt))
    return recommendations[:max_recommendations]


def _score_candidate(
    *,
    required_available_count: int,
    required_total: int,
    optional_available_count: int,
    optional_total: int,
    overloaded_in_team_count: int,
    team_size: int,
) -> float:
    required_ratio = (
        required_available_count / required_total if required_total > 0 else 1.0
    )
    optional_ratio = (
        optional_available_count / optional_total if optional_total > 0 else 0.0
    )
    overload_ratio = overloaded_in_team_count / team_size if team_size > 0 else 0.0
    return (
        SCORE_REQUIRED_WEIGHT * required_ratio
        + SCORE_OPTIONAL_WEIGHT * optional_ratio
        - SCORE_OVERLOAD_PENALTY_WEIGHT * overload_ratio
    )


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


@dataclass(frozen=True, slots=True)
class TeamOverlapSummary:
    full_team_minutes: float
    majority_minutes: float
    total_window_minutes: float


def team_overlap_summary(
    availability: list[EmployeeAvailability],
    *,
    range_start: datetime,
    range_end: datetime,
    majority_threshold: float = 0.5,
) -> TeamOverlapSummary:
    """Считает пересечение доступности команды (Tteam из ТЗ §8).

    full_team_minutes — минуты, когда доступны все сотрудники команды.
    majority_minutes — минуты, когда доступно более `majority_threshold` команды.
    total_window_minutes — общая длительность запрошенного окна.
    """
    total_window_minutes = max(0.0, (range_end - range_start).total_seconds() / 60)
    if not availability or range_start >= range_end:
        return TeamOverlapSummary(
            full_team_minutes=0.0,
            majority_minutes=0.0,
            total_window_minutes=total_window_minutes,
        )

    boundaries: set[datetime] = {range_start, range_end}
    for employee in availability:
        for window in employee.available_windows:
            boundaries.add(max(window.start_dt, range_start))
            boundaries.add(min(window.end_dt, range_end))
    ordered = sorted(point for point in boundaries if range_start <= point <= range_end)

    team_size = len(availability)
    majority_min_count = max(1, int(team_size * majority_threshold) + 1) if team_size > 1 else 1
    full_minutes = 0.0
    majority_minutes_value = 0.0
    for current, nxt in zip(ordered, ordered[1:], strict=False):
        if nxt <= current:
            continue
        mid = current + (nxt - current) / 2
        active = sum(
            1
            for employee in availability
            if any(window.start_dt <= mid < window.end_dt for window in employee.available_windows)
        )
        duration_minutes = (nxt - current).total_seconds() / 60
        if active == team_size:
            full_minutes += duration_minutes
        if active >= majority_min_count:
            majority_minutes_value += duration_minutes
    return TeamOverlapSummary(
        full_team_minutes=full_minutes,
        majority_minutes=majority_minutes_value,
        total_window_minutes=total_window_minutes,
    )
