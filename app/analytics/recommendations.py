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
                reason=f"График обновлялся {snapshot.days_since_update} дн. назад.",
                severity="medium",
                action="Запросите подтверждение актуального графика у сотрудника или руководителя.",
            )
        )
    if snapshot.conflict_rate >= HIGH_CONFLICT_RATE_THRESHOLD:
        recommendations.append(
            Recommendation(
                code="high_conflict_rate",
                reason=f"Доля конфликтов: {snapshot.conflict_rate:.0%}.",
                severity="high",
                action="Проверьте регулярные встречи, выходящие за рамки графика.",
            )
        )
    if snapshot.load_level > HIGH_LOAD_LEVEL_THRESHOLD:
        recommendations.append(
            Recommendation(
                code="high_load_level",
                reason=f"Загрузка: {snapshot.load_level:.0%} от рабочих часов.",
                severity="high",
                action="Снизьте нагрузку по встречам или скорректируйте график.",
            )
        )
    if snapshot.risk_score >= HIGH_RISK_THRESHOLD:
        recommendations.append(
            Recommendation(
                code="high_risk_score",
                reason=f"Индекс риска: {snapshot.risk_score:.2f}.",
                severity="critical" if snapshot.risk_level == "critical" else "high",
                action="Возьмите сотрудника в приоритет на review с руководителем.",
            )
        )
    if snapshot.outside_events_count > 0:
        recommendations.append(
            Recommendation(
                code="events_outside_schedule",
                reason=f"Встреч вне графика: {snapshot.outside_events_count}.",
                severity="medium",
                action="Перенесите встречи в рабочее время или обновите исключения графика.",
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
                "Тайм-зона сотрудника отличается от тайм-зоны графика или событий: "
                + ", ".join(sorted(mismatched_timezones))
            ),
            severity="medium",
            action="Проверьте настройки тайм-зон перед пересчётом показателей.",
        )
    ]
