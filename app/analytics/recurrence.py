import logging
from datetime import datetime, timezone

from dateutil.rrule import rrulestr

from app.analytics.meeting import EventInterval
from app.models.activity_event import ActivityEvent

logger = logging.getLogger(__name__)


def expand_event(
    event: ActivityEvent,
    range_start: datetime,
    range_end: datetime,
) -> list[EventInterval]:
    """Развернуть событие в occurrences в окне [range_start, range_end).

    Если у события есть recurrence_rule — парсит RRULE c dtstart=event.start_dt
    и генерирует EventInterval для каждого вхождения в окно, копируя длительность
    master-события. Иначе возвращает один EventInterval если master пересекает окно.

    При невалидном recurrence_rule делает graceful degrade: возвращает master как
    одиночное событие и логирует ошибку.
    """
    duration = event.end_dt - event.start_dt

    if event.recurrence_rule is None:
        if event.end_dt > range_start and event.start_dt < range_end:
            return [
                EventInterval(
                    start_dt=event.start_dt,
                    end_dt=event.end_dt,
                    is_outside_schedule=event.is_outside_schedule,
                )
            ]
        return []

    try:
        rule = rrulestr(event.recurrence_rule, dtstart=event.start_dt)
    except (ValueError, TypeError) as exc:
        logger.warning(
            "Invalid recurrence_rule on event %s: %s; falling back to master only",
            event.id,
            exc,
        )
        if event.end_dt > range_start and event.start_dt < range_end:
            return [
                EventInterval(
                    start_dt=event.start_dt,
                    end_dt=event.end_dt,
                    is_outside_schedule=event.is_outside_schedule,
                )
            ]
        return []

    after = _align_timezone(range_start, event.start_dt) - duration
    before = _align_timezone(range_end, event.start_dt)
    occurrences = rule.between(after=after, before=before, inc=False)

    intervals: list[EventInterval] = []
    for occurrence_start in occurrences:
        occurrence_end = occurrence_start + duration
        if occurrence_end <= range_start or occurrence_start >= range_end:
            continue
        intervals.append(
            EventInterval(
                start_dt=occurrence_start,
                end_dt=occurrence_end,
                is_outside_schedule=event.is_outside_schedule,
            )
        )
    return intervals


def _align_timezone(value: datetime, reference: datetime) -> datetime:
    """rrule.between требует, чтобы naive/aware соответствовал dtstart."""
    if reference.tzinfo is None and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    if reference.tzinfo is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
