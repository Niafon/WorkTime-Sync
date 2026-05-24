from app.analytics import MetricSnapshot, RecommendationContext, generate_recommendations


def _snapshot(**overrides: object) -> MetricSnapshot:
    values = {
        "days_since_update": 0,
        "actuality_score": 1.0,
        "outside_events_count": 0,
        "total_events_count": 0,
        "conflict_rate": 0.0,
        "load_level": 0.5,
        "risk_score": 0.0,
        "risk_level": "low",
    }
    values.update(overrides)
    return MetricSnapshot(**values)  # type: ignore[arg-type]


def _codes(context: RecommendationContext) -> list[str]:
    return [recommendation.code for recommendation in generate_recommendations(context)]


def test_outdated_schedule_rule() -> None:
    context = RecommendationContext(
        employee_timezone="Europe/Moscow",
        metric=_snapshot(days_since_update=90, actuality_score=0.0),
    )

    assert _codes(context) == ["outdated_schedule"]


def test_high_conflict_rate_rule() -> None:
    context = RecommendationContext(
        employee_timezone="Europe/Moscow",
        metric=_snapshot(outside_events_count=2, total_events_count=4, conflict_rate=0.5),
    )

    assert "high_conflict_rate" in _codes(context)


def test_high_load_level_rule() -> None:
    context = RecommendationContext(
        employee_timezone="Europe/Moscow",
        metric=_snapshot(load_level=1.1),
    )

    assert _codes(context) == ["high_load_level"]


def test_high_risk_score_rule() -> None:
    context = RecommendationContext(
        employee_timezone="Europe/Moscow",
        metric=_snapshot(risk_score=0.6, risk_level="high"),
    )

    recommendation = generate_recommendations(context)[0]
    assert recommendation.code == "high_risk_score"
    assert recommendation.severity == "high"


def test_events_outside_schedule_rule() -> None:
    context = RecommendationContext(
        employee_timezone="Europe/Moscow",
        metric=_snapshot(outside_events_count=1, total_events_count=5),
    )

    assert _codes(context) == ["events_outside_schedule"]


def test_timezone_mismatch_rule_from_schedule_and_events() -> None:
    context = RecommendationContext(
        employee_timezone="Europe/Moscow",
        metric=_snapshot(),
        schedule_timezone="Asia/Yekaterinburg",
        event_timezones=("Europe/Moscow", "UTC"),
    )

    recommendation = generate_recommendations(context)[0]
    assert recommendation.code == "timezone_mismatch_suspicion"
    assert "Asia/Yekaterinburg" in recommendation.reason
    assert "UTC" in recommendation.reason


def test_no_metric_still_checks_timezone_mismatch() -> None:
    context = RecommendationContext(
        employee_timezone="Europe/Moscow",
        schedule_timezone="UTC",
    )

    assert _codes(context) == ["timezone_mismatch_suspicion"]


def test_no_issues_returns_empty_list() -> None:
    context = RecommendationContext(
        employee_timezone="Europe/Moscow",
        metric=_snapshot(),
        schedule_timezone="Europe/Moscow",
        event_timezones=("Europe/Moscow",),
    )

    assert generate_recommendations(context) == []
