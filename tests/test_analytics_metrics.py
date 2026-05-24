from datetime import UTC, date, datetime, time

import pytest

from app.analytics import (
    CRITICAL_RISK_THRESHOLD,
    HIGH_RISK_THRESHOLD,
    MEDIUM_RISK_THRESHOLD,
    EventInterval,
    MetricSnapshot,
    RecommendationContext,
    WorkScheduleWindow,
    actuality_score,
    busy_hours,
    conflict_rate,
    count_outside_events,
    days_since_update,
    generate_recommendations,
    is_event_outside_schedule,
    load_level,
    risk_level,
    risk_score,
    work_hours,
)


def test_days_since_update_and_actuality_score() -> None:
    last_updated_at = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)

    days = days_since_update(last_updated_at, date(2026, 5, 24))

    assert days == 23
    assert actuality_score(days) == pytest.approx(1 - 23 / 90)


def test_actuality_score_floor_and_future_update_guard() -> None:
    future_update = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)

    assert days_since_update(future_update, date(2026, 5, 24)) == 0
    assert actuality_score(180) == 0.0


def test_conflict_rate_handles_empty_events() -> None:
    assert conflict_rate(outside_events_count=0, total_events_count=0) == 0.0
    assert conflict_rate(outside_events_count=2, total_events_count=4) == 0.5


def test_load_level_avoids_division_by_zero() -> None:
    assert load_level(busy_hours_value=3, work_hours_value=0) == 0.0
    assert load_level(busy_hours_value=6, work_hours_value=8) == 0.75


def test_risk_score_formula() -> None:
    score = risk_score(
        actuality_score_value=0.8,
        conflict_rate_value=0.5,
        load_level_value=0.75,
        hr_factor=0.2,
    )

    assert score == pytest.approx(0.3 * 0.2 + 0.3 * 0.5 + 0.25 * 0.75 + 0.15 * 0.2)


@pytest.mark.parametrize(
    ("score", "expected_level"),
    [
        (MEDIUM_RISK_THRESHOLD - 0.01, "low"),
        (MEDIUM_RISK_THRESHOLD, "medium"),
        (HIGH_RISK_THRESHOLD, "high"),
        (CRITICAL_RISK_THRESHOLD, "critical"),
    ],
)
def test_risk_level_thresholds(score: float, expected_level: str) -> None:
    assert risk_level(score) == expected_level


def test_work_hours_and_outside_schedule_detection() -> None:
    schedule = WorkScheduleWindow(
        work_days=(0, 1, 2, 3, 4),
        start_time=time(9, 0),
        end_time=time(18, 0),
    )

    assert work_hours(schedule) == 9
    assert (
        is_event_outside_schedule(
            start_dt=datetime(2026, 5, 25, 10, 0, tzinfo=UTC),
            end_dt=datetime(2026, 5, 25, 11, 0, tzinfo=UTC),
            schedule=schedule,
        )
        is False
    )
    assert (
        is_event_outside_schedule(
            start_dt=datetime(2026, 5, 25, 8, 30, tzinfo=UTC),
            end_dt=datetime(2026, 5, 25, 9, 30, tzinfo=UTC),
            schedule=schedule,
        )
        is True
    )


def test_busy_hours_is_deterministic_and_ignores_negative_intervals() -> None:
    events = [
        EventInterval(
            start_dt=datetime(2026, 5, 25, 10, 0, tzinfo=UTC),
            end_dt=datetime(2026, 5, 25, 11, 30, tzinfo=UTC),
        ),
        EventInterval(
            start_dt=datetime(2026, 5, 25, 14, 0, tzinfo=UTC),
            end_dt=datetime(2026, 5, 25, 13, 0, tzinfo=UTC),
        ),
    ]

    assert busy_hours(events) == 1.5
    assert busy_hours(events) == 1.5


def test_count_outside_events_empty_and_with_schedule() -> None:
    schedule = WorkScheduleWindow(
        work_days=(0, 1, 2, 3, 4),
        start_time=time(9, 0),
        end_time=time(18, 0),
    )
    events = [
        EventInterval(
            start_dt=datetime(2026, 5, 25, 10, 0, tzinfo=UTC),
            end_dt=datetime(2026, 5, 25, 11, 0, tzinfo=UTC),
        ),
        EventInterval(
            start_dt=datetime(2026, 5, 30, 10, 0, tzinfo=UTC),
            end_dt=datetime(2026, 5, 30, 11, 0, tzinfo=UTC),
        ),
    ]

    assert count_outside_events([]) == 0
    assert count_outside_events(events, schedule) == 1


def test_recommendations_for_empty_low_risk_snapshot() -> None:
    snapshot = MetricSnapshot(
        days_since_update=0,
        actuality_score=1.0,
        outside_events_count=0,
        total_events_count=0,
        conflict_rate=0.0,
        load_level=0.0,
        risk_score=0.0,
        risk_level="low",
    )

    context = RecommendationContext(employee_timezone="Europe/Moscow", metric=snapshot)

    assert generate_recommendations(context) == []


def test_recommendations_for_stale_conflicting_high_risk_snapshot() -> None:
    snapshot = MetricSnapshot(
        days_since_update=45,
        actuality_score=0.5,
        outside_events_count=3,
        total_events_count=4,
        conflict_rate=0.75,
        load_level=0.8,
        risk_score=0.65,
        risk_level="high",
    )

    context = RecommendationContext(employee_timezone="Europe/Moscow", metric=snapshot)

    assert [recommendation.code for recommendation in generate_recommendations(context)] == [
        "high_conflict_rate",
        "high_risk_score",
        "events_outside_schedule",
    ]
