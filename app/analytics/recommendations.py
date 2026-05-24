from dataclasses import dataclass

from app.analytics.metrics import ACTUALITY_DECAY_DAYS, HIGH_RISK_THRESHOLD, MetricSnapshot

HIGH_CONFLICT_RATE_THRESHOLD = 0.35
HIGH_LOAD_LEVEL_THRESHOLD = 1.0


@dataclass(frozen=True, slots=True)
class RecommendationContext:
    employee_timezone: str
    metric: MetricSnapshot | None = None
    schedule_timezone: str | None = None
    event_timezones: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Recommendation:
    code: str
    reason: str
    severity: str
    action: str


def generate_recommendations(context: RecommendationContext) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    snapshot = context.metric

    if snapshot is None:
        recommendations.extend(_timezone_mismatch_recommendations(context))
        return recommendations

    if snapshot.days_since_update >= ACTUALITY_DECAY_DAYS:
        recommendations.append(
            Recommendation(
                code="outdated_schedule",
                reason=f"Schedule was updated {snapshot.days_since_update} days ago.",
                severity="medium",
                action="Ask the employee or manager to confirm the current work schedule.",
            )
        )
    if snapshot.conflict_rate >= HIGH_CONFLICT_RATE_THRESHOLD:
        recommendations.append(
            Recommendation(
                code="high_conflict_rate",
                reason=f"Conflict rate is {snapshot.conflict_rate:.0%}.",
                severity="high",
                action="Review recurring events that conflict with the schedule.",
            )
        )
    if snapshot.load_level > HIGH_LOAD_LEVEL_THRESHOLD:
        recommendations.append(
            Recommendation(
                code="high_load_level",
                reason=f"Load level is {snapshot.load_level:.0%} of scheduled work hours.",
                severity="high",
                action="Reduce meeting load or adjust the schedule.",
            )
        )
    if snapshot.risk_score >= HIGH_RISK_THRESHOLD:
        recommendations.append(
            Recommendation(
                code="high_risk_score",
                reason=f"Risk score is {snapshot.risk_score:.2f}.",
                severity="critical" if snapshot.risk_level == "critical" else "high",
                action="Prioritize manager review for this employee.",
            )
        )
    if snapshot.outside_events_count > 0:
        recommendations.append(
            Recommendation(
                code="events_outside_schedule",
                reason=f"{snapshot.outside_events_count} events are outside the schedule.",
                severity="medium",
                action="Move events into working hours or update schedule exceptions.",
            )
        )

    recommendations.extend(_timezone_mismatch_recommendations(context))

    return recommendations


def _timezone_mismatch_recommendations(context: RecommendationContext) -> list[Recommendation]:
    mismatched_timezones = {
        timezone
        for timezone in (*context.event_timezones, context.schedule_timezone)
        if timezone is not None and timezone != context.employee_timezone
    }
    if not mismatched_timezones:
        return []

    return [
        Recommendation(
            code="timezone_mismatch_suspicion",
            reason=(
                "Employee timezone differs from schedule or event timezone: "
                + ", ".join(sorted(mismatched_timezones))
            ),
            severity="medium",
            action="Verify timezone settings before recalculating metrics.",
        )
    ]
