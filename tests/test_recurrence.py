from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.analytics.recurrence import expand_event


def _make_event(
    *,
    start_dt: datetime,
    end_dt: datetime,
    recurrence_rule: str | None = None,
    is_outside_schedule: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        start_dt=start_dt,
        end_dt=end_dt,
        recurrence_rule=recurrence_rule,
        is_outside_schedule=is_outside_schedule,
    )


def test_non_recurring_event_inside_window_returns_single_interval() -> None:
    start = datetime(2026, 5, 10, 10, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)
    event = _make_event(start_dt=start, end_dt=end)

    intervals = expand_event(
        event,
        range_start=datetime(2026, 5, 1, tzinfo=UTC),
        range_end=datetime(2026, 5, 31, tzinfo=UTC),
    )

    assert len(intervals) == 1
    assert intervals[0].start_dt == start
    assert intervals[0].end_dt == end


def test_non_recurring_event_outside_window_returns_empty() -> None:
    start = datetime(2026, 4, 10, 10, 0, tzinfo=UTC)
    event = _make_event(start_dt=start, end_dt=start + timedelta(hours=1))

    intervals = expand_event(
        event,
        range_start=datetime(2026, 5, 1, tzinfo=UTC),
        range_end=datetime(2026, 5, 31, tzinfo=UTC),
    )

    assert intervals == []


def test_daily_count_expansion_keeps_duration() -> None:
    start = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)
    event = _make_event(
        start_dt=start,
        end_dt=start + timedelta(minutes=45),
        recurrence_rule="FREQ=DAILY;COUNT=5",
    )

    intervals = expand_event(
        event,
        range_start=datetime(2026, 5, 1, tzinfo=UTC),
        range_end=datetime(2026, 5, 11, tzinfo=UTC),
    )

    assert len(intervals) == 5
    for i, interval in enumerate(intervals):
        expected_start = start + timedelta(days=i)
        assert interval.start_dt == expected_start
        assert interval.end_dt - interval.start_dt == timedelta(minutes=45)


def test_weekly_byday_expansion_picks_correct_weekdays() -> None:
    # 2026-05-04 is Monday
    start = datetime(2026, 5, 4, 10, 0, tzinfo=UTC)
    event = _make_event(
        start_dt=start,
        end_dt=start + timedelta(hours=1),
        recurrence_rule="FREQ=WEEKLY;BYDAY=MO,WE;COUNT=8",
    )

    intervals = expand_event(
        event,
        range_start=datetime(2026, 5, 1, tzinfo=UTC),
        range_end=datetime(2026, 6, 30, tzinfo=UTC),
    )

    assert len(intervals) == 8
    for interval in intervals:
        assert interval.start_dt.weekday() in (0, 2)


def test_until_clips_before_window_end() -> None:
    start = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)
    event = _make_event(
        start_dt=start,
        end_dt=start + timedelta(hours=1),
        recurrence_rule="FREQ=DAILY;UNTIL=20260505T235959Z",
    )

    intervals = expand_event(
        event,
        range_start=datetime(2026, 5, 1, tzinfo=UTC),
        range_end=datetime(2026, 6, 1, tzinfo=UTC),
    )

    assert len(intervals) == 5
    assert intervals[-1].start_dt == datetime(2026, 5, 5, 10, 0, tzinfo=UTC)


def test_window_clips_recurrence_to_subrange() -> None:
    start = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)
    event = _make_event(
        start_dt=start,
        end_dt=start + timedelta(hours=1),
        recurrence_rule="FREQ=DAILY;COUNT=30",
    )

    intervals = expand_event(
        event,
        range_start=datetime(2026, 5, 10, tzinfo=UTC),
        range_end=datetime(2026, 5, 15, tzinfo=UTC),
    )

    assert len(intervals) == 5
    assert intervals[0].start_dt == datetime(2026, 5, 10, 10, 0, tzinfo=UTC)
    assert intervals[-1].start_dt == datetime(2026, 5, 14, 10, 0, tzinfo=UTC)


def test_invalid_rrule_falls_back_to_master_event() -> None:
    start = datetime(2026, 5, 10, 10, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)
    event = _make_event(
        start_dt=start,
        end_dt=end,
        recurrence_rule="not-a-valid-rrule",
    )

    intervals = expand_event(
        event,
        range_start=datetime(2026, 5, 1, tzinfo=UTC),
        range_end=datetime(2026, 5, 31, tzinfo=UTC),
    )

    assert len(intervals) == 1
    assert intervals[0].start_dt == start
    assert intervals[0].end_dt == end


def test_is_outside_schedule_propagates_to_all_occurrences() -> None:
    start = datetime(2026, 5, 1, 21, 0, tzinfo=UTC)
    event = _make_event(
        start_dt=start,
        end_dt=start + timedelta(minutes=30),
        recurrence_rule="FREQ=DAILY;COUNT=3",
        is_outside_schedule=True,
    )

    intervals = expand_event(
        event,
        range_start=datetime(2026, 5, 1, tzinfo=UTC),
        range_end=datetime(2026, 5, 10, tzinfo=UTC),
    )

    assert len(intervals) == 3
    assert all(interval.is_outside_schedule for interval in intervals)
