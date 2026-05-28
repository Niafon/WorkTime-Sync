from dataclasses import dataclass

from app.analytics.metrics import MetricSnapshot

SEVERITY_WEIGHT: dict[str, float] = {
    "critical": 1.0,
    "high": 0.75,
    "medium": 0.5,
    "low": 0.25,
}

CODE_BASE_WEIGHT: dict[str, float] = {
    "outdated_schedule": 0.90,
    "high_risk_score": 0.85,
    "high_conflict_rate": 0.70,
    "high_load_level": 0.60,
    "events_outside_schedule": 0.55,
    "timezone_mismatch_suspicion": 0.40,
}

SEVERITY_TO_DUE_DAYS: dict[str, int] = {
    "critical": 2,
    "high": 5,
    "medium": 10,
    "low": 20,
}

REQUEST_AGING_DAILY_DECAY = 0.05
DUE_OVERDUE_PER_DAY = 0.08

CODE_TITLE_RU: dict[str, str] = {
    "outdated_schedule": "Подтвердить или обновить рабочий график",
    "high_conflict_rate": "Снизить количество встреч вне графика",
    "high_load_level": "Снизить нагрузку сотрудника",
    "high_risk_score": "Взять сотрудника в приоритет на review",
    "events_outside_schedule": "Разобрать встречи вне рабочего времени",
    "timezone_mismatch_suspicion": "Проверить часовой пояс сотрудника",
}


@dataclass(frozen=True, slots=True)
class PriorityInputs:
    metric: MetricSnapshot | None
    severity: str
    code: str
    days_since_request: int = 0
    days_overdue: int = 0


def compute_priority(inputs: PriorityInputs) -> float:
    """Балл приоритета в [0..100] на основе severity, кода рекомендации,
    риска сотрудника, давности запроса и просрочки дедлайна.
    """
    risk = inputs.metric.risk_score if inputs.metric is not None else 0.5
    actuality_gap = 1.0 - (
        inputs.metric.actuality_score if inputs.metric is not None else 0.0
    )

    base = 50.0 * SEVERITY_WEIGHT.get(inputs.severity, 0.5)
    code_bonus = 20.0 * CODE_BASE_WEIGHT.get(inputs.code, 0.5)
    risk_bonus = 20.0 * risk
    actuality_bonus = 10.0 * actuality_gap

    aging_factor = min(1.0, max(0, inputs.days_since_request) * REQUEST_AGING_DAILY_DECAY)
    overdue_factor = min(1.0, max(0, inputs.days_overdue) * DUE_OVERDUE_PER_DAY)
    aging_bonus = 25.0 * aging_factor
    overdue_bonus = 50.0 * overdue_factor

    total = base + code_bonus + risk_bonus + actuality_bonus + aging_bonus + overdue_bonus
    return round(min(100.0, max(0.0, total)), 2)


def build_reason(
    code: str,
    metric: MetricSnapshot | None,
    base_reason: str,
) -> str:
    """Формирует объяснимое reason из base_reason плюс ключевые метрики."""
    parts: list[str] = [base_reason.strip()]
    if metric is None:
        return parts[0]

    digest: str | None = None
    if code == "outdated_schedule":
        digest = (
            f"актуальность {metric.actuality_score:.2f}, "
            f"без обновлений {metric.days_since_update} дн."
        )
    elif code == "high_risk_score":
        digest = f"риск {metric.risk_level} ({metric.risk_score:.2f})"
    elif code == "high_conflict_rate":
        digest = f"конфликтов {metric.conflict_rate:.0%}"
    elif code == "high_load_level":
        digest = f"загрузка {metric.load_level:.0%}"
    elif code == "events_outside_schedule":
        digest = (
            f"вне графика {metric.outside_events_count} из "
            f"{metric.total_events_count}"
        )
    elif code == "timezone_mismatch_suspicion":
        digest = f"расхождение часовых поясов {metric.zone_factor:.0%}"

    if digest:
        parts.append(digest)
    return " · ".join(parts)
