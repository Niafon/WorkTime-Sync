import pytest

from app.analytics.metrics import MetricSnapshot
from app.analytics.roadmap_priority import (
    PriorityInputs,
    build_reason,
    compute_priority,
)


def _make_snapshot(**overrides) -> MetricSnapshot:
    base: dict = dict(
        days_since_update=120,
        actuality_score=0.0,
        outside_events_count=2,
        total_events_count=4,
        conflict_rate=0.5,
        load_level=1.2,
        zone_factor=0.3,
        hr_factor=0.4,
        risk_score=0.75,
        risk_level="high",
    )
    base.update(overrides)
    return MetricSnapshot(**base)


def test_priority_critical_outdated_schedule_is_high() -> None:
    snapshot = _make_snapshot()
    score = compute_priority(
        PriorityInputs(
            metric=snapshot, severity="critical", code="outdated_schedule"
        )
    )
    assert score >= 80


def test_priority_low_severity_timezone_is_lower_than_critical_outdated() -> None:
    snapshot = _make_snapshot(risk_score=0.1, actuality_score=0.9)
    low = compute_priority(
        PriorityInputs(
            metric=snapshot, severity="low", code="timezone_mismatch_suspicion"
        )
    )
    high = compute_priority(
        PriorityInputs(
            metric=_make_snapshot(),
            severity="critical",
            code="outdated_schedule",
        )
    )
    assert low < high


def test_priority_increases_with_days_since_request() -> None:
    snapshot = _make_snapshot()
    fresh = compute_priority(
        PriorityInputs(
            metric=snapshot,
            severity="medium",
            code="outdated_schedule",
            days_since_request=0,
        )
    )
    aged = compute_priority(
        PriorityInputs(
            metric=snapshot,
            severity="medium",
            code="outdated_schedule",
            days_since_request=15,
        )
    )
    assert aged > fresh


def test_priority_increases_with_overdue() -> None:
    snapshot = _make_snapshot()
    on_time = compute_priority(
        PriorityInputs(
            metric=snapshot,
            severity="high",
            code="high_risk_score",
            days_overdue=0,
        )
    )
    overdue = compute_priority(
        PriorityInputs(
            metric=snapshot,
            severity="high",
            code="high_risk_score",
            days_overdue=12,
        )
    )
    assert overdue > on_time


def test_priority_capped_at_100() -> None:
    snapshot = _make_snapshot(risk_score=1.0, actuality_score=0.0)
    score = compute_priority(
        PriorityInputs(
            metric=snapshot,
            severity="critical",
            code="outdated_schedule",
            days_since_request=100,
            days_overdue=100,
        )
    )
    assert score <= 100.0


def test_priority_without_metric_uses_neutral_defaults() -> None:
    score = compute_priority(
        PriorityInputs(metric=None, severity="medium", code="outdated_schedule")
    )
    assert 0 <= score <= 100


@pytest.mark.parametrize(
    "code,fragment",
    [
        ("outdated_schedule", "актуальность"),
        ("high_conflict_rate", "конфликтов"),
        ("high_load_level", "загрузка"),
        ("high_risk_score", "риск"),
        ("events_outside_schedule", "вне графика"),
        ("timezone_mismatch_suspicion", "часовых поясов"),
    ],
)
def test_build_reason_includes_metric_digest(code: str, fragment: str) -> None:
    snapshot = _make_snapshot()
    reason = build_reason(code, snapshot, "Базовое объяснение.")
    assert "Базовое объяснение." in reason
    assert fragment in reason


def test_build_reason_without_metric_returns_base() -> None:
    reason = build_reason("outdated_schedule", None, "Только базовое.")
    assert reason == "Только базовое."
