from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.analytics import (
    CRITICAL_RISK_THRESHOLD,
    HIGH_RISK_THRESHOLD,
    MEDIUM_RISK_THRESHOLD,
    EmployeeAvailability,
    EventInterval,
    MetricSnapshot,
    RecommendationContext,
    TimeWindow,
    WorkScheduleWindow,
    actuality_score,
    busy_hours,
    conflict_rate,
    count_outside_events,
    days_since_update,
    generate_recommendations,
    hr_factor,
    is_event_outside_schedule,
    load_level,
    risk_level,
    risk_score,
    team_overlap_summary,
    work_hours,
    zone_factor,
)
from app.analytics.metrics import (
    RISK_ACTUALITY_WEIGHT,
    RISK_CONFLICT_WEIGHT,
    RISK_HR_WEIGHT,
    RISK_LOAD_WEIGHT,
    RISK_ZONE_WEIGHT,
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


def test_days_since_update_prefers_confirmed_at_when_newer() -> None:
    last_updated = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    confirmed = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)

    days = days_since_update(last_updated, date(2026, 5, 24), confirmed_at=confirmed)

    assert days == 4


def test_days_since_update_keeps_last_updated_when_confirmed_older() -> None:
    last_updated = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    confirmed = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)

    days = days_since_update(last_updated, date(2026, 5, 24), confirmed_at=confirmed)

    assert days == 23


def test_days_since_update_confirmed_none_is_noop() -> None:
    last_updated = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)

    assert days_since_update(last_updated, date(2026, 5, 24), confirmed_at=None) == 23


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
        zone_factor_value=0.4,
        hr_factor_value=0.2,
    )

    expected = (
        RISK_ACTUALITY_WEIGHT * (1 - 0.8)
        + RISK_CONFLICT_WEIGHT * 0.5
        + RISK_LOAD_WEIGHT * 0.75
        + RISK_ZONE_WEIGHT * 0.4
        + RISK_HR_WEIGHT * 0.2
    )
    assert score == pytest.approx(expected)


def test_zone_factor_no_events_returns_zero() -> None:
    assert zone_factor("Europe/Moscow", []) == 0.0


def test_zone_factor_counts_other_timezones() -> None:
    timezones = ["Europe/Moscow", "Asia/Tokyo", "Asia/Tokyo", "Europe/Moscow"]
    assert zone_factor("Europe/Moscow", timezones) == pytest.approx(0.5)


def test_hr_factor_balanced_sources_returns_zero() -> None:
    assert hr_factor(hr_events_count=5, calendar_events_count=5) == 0.0
    assert hr_factor(hr_events_count=0, calendar_events_count=0) == 0.0


def test_hr_factor_full_imbalance_returns_one() -> None:
    assert hr_factor(hr_events_count=0, calendar_events_count=4) == 1.0
    assert hr_factor(hr_events_count=6, calendar_events_count=0) == 1.0


def test_hr_factor_partial_imbalance() -> None:
    assert hr_factor(hr_events_count=3, calendar_events_count=1) == pytest.approx(0.5)


def test_team_overlap_summary_full_overlap_for_identical_windows() -> None:
    range_start = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    range_end = datetime(2026, 5, 25, 11, 0, tzinfo=UTC)
    window = TimeWindow(start_dt=range_start, end_dt=range_end)
    availability = [
        EmployeeAvailability(employee_id="a", available_windows=(window,)),
        EmployeeAvailability(employee_id="b", available_windows=(window,)),
    ]

    summary = team_overlap_summary(
        availability,
        range_start=range_start,
        range_end=range_end,
    )

    assert summary.total_window_minutes == 120
    assert summary.full_team_minutes == 120
    assert summary.majority_minutes == 120


def test_team_overlap_summary_partial_overlap_reflects_disjoint_windows() -> None:
    range_start = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    range_end = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    availability = [
        EmployeeAvailability(
            employee_id="a",
            available_windows=(TimeWindow(range_start, range_start + timedelta(hours=2)),),
        ),
        EmployeeAvailability(
            employee_id="b",
            available_windows=(TimeWindow(range_start + timedelta(hours=1), range_end),),
        ),
    ]

    summary = team_overlap_summary(
        availability,
        range_start=range_start,
        range_end=range_end,
    )

    assert summary.total_window_minutes == 180
    assert summary.full_team_minutes == 60  # 10:00–11:00 общий для обоих
    # При размере команды 2 «строгое большинство» совпадает с полным составом.
    assert summary.majority_minutes == 60


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
        zone_factor=0.0,
        hr_factor=0.0,
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
        zone_factor=0.0,
        hr_factor=0.0,
        risk_score=0.65,
        risk_level="high",
    )

    context = RecommendationContext(employee_timezone="Europe/Moscow", metric=snapshot)

    assert [recommendation.code for recommendation in generate_recommendations(context)] == [
        "high_conflict_rate",
        "high_risk_score",
        "events_outside_schedule",
    ]
