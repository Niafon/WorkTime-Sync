from dataclasses import dataclass
from datetime import datetime

from app.analytics.availability import WorkScheduleWindow, is_event_outside_schedule


@dataclass(frozen=True, slots=True)
class EventInterval:
    start_dt: datetime
    end_dt: datetime
    is_outside_schedule: bool = False


def busy_hours(events: list[EventInterval]) -> float:
    return sum(max(0.0, (event.end_dt - event.start_dt).total_seconds() / 3600) for event in events)


def count_outside_events(
    events: list[EventInterval],
    schedule: WorkScheduleWindow | None = None,
) -> int:
    if schedule is None:
        return sum(1 for event in events if event.is_outside_schedule)
    return sum(
        1
        for event in events
        if is_event_outside_schedule(
            start_dt=event.start_dt,
            end_dt=event.end_dt,
            schedule=schedule,
        )
    )
