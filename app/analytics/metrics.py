from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

ACTUALITY_DECAY_DAYS = 90

RISK_ACTUALITY_WEIGHT = 0.25
RISK_CONFLICT_WEIGHT = 0.25
RISK_LOAD_WEIGHT = 0.20
RISK_ZONE_WEIGHT = 0.15
RISK_HR_WEIGHT = 0.15

MEDIUM_RISK_THRESHOLD = 0.35
HIGH_RISK_THRESHOLD = 0.60
CRITICAL_RISK_THRESHOLD = 0.80


@dataclass(frozen=True, slots=True)
class MetricSnapshot:
    days_since_update: int
    actuality_score: float
    outside_events_count: int
    total_events_count: int
    conflict_rate: float
    load_level: float
    risk_score: float
    risk_level: str
    zone_factor: float = 0.0
    hr_factor: float = 0.0


def days_since_update(
    last_updated_at: datetime,
    today: date,
    confirmed_at: datetime | None = None,
) -> int:
    """Дней между сегодня и последним обновлением графика.

    Если `last_updated_at` или `confirmed_at` оказались в будущем (битая дата
    при импорте), считаем их как «сегодня». Без этого Ai становился 1.0 у
    сотрудника с future-датой — система ошибочно считала график идеальным.
    """
    reference = max(last_updated_at, confirmed_at) if confirmed_at else last_updated_at
    reference_date = min(reference.date(), today)
    return max(0, (today - reference_date).days)


def actuality_score(days_since_update_value: int) -> float:
    return max(0.0, 1.0 - days_since_update_value / ACTUALITY_DECAY_DAYS)


def conflict_rate(outside_events_count: int, total_events_count: int) -> float:
    if total_events_count <= 0:
        return 0.0
    return outside_events_count / total_events_count


def load_level(busy_hours_value: float, work_hours_value: float) -> float:
    if work_hours_value <= 0:
        return 0.0
    return busy_hours_value / work_hours_value


def zone_factor(employee_timezone: str, event_timezones: Iterable[str]) -> float:
    """Доля событий с отличающимся от сотрудника часовым поясом (Zi из ТЗ §10).

    Возвращает 0.0, если событий нет, иначе |{e: tz(e) != tz_employee}| / |E|.
    """
    timezones = list(event_timezones)
    if not timezones:
        return 0.0
    other = sum(1 for tz in timezones if tz != employee_timezone)
    return other / len(timezones)


def hr_factor(hr_events_count: int, calendar_events_count: int) -> float:
    """Нормированное расхождение между HR и календарём (Hi из ТЗ §10).

    Hi = |N_hr − N_cal| / (N_hr + N_cal). 0.0 при отсутствии обоих источников.
    """
    total = hr_events_count + calendar_events_count
    if total <= 0:
        return 0.0
    return abs(hr_events_count - calendar_events_count) / total


def risk_score(
    *,
    actuality_score_value: float,
    conflict_rate_value: float,
    load_level_value: float,
    zone_factor_value: float,
    hr_factor_value: float,
) -> float:
    return (
        RISK_ACTUALITY_WEIGHT * (1.0 - actuality_score_value)
        + RISK_CONFLICT_WEIGHT * conflict_rate_value
        + RISK_LOAD_WEIGHT * load_level_value
        + RISK_ZONE_WEIGHT * zone_factor_value
        + RISK_HR_WEIGHT * hr_factor_value
    )


def risk_level(risk_score_value: float) -> str:
    if risk_score_value >= CRITICAL_RISK_THRESHOLD:
        return "critical"
    if risk_score_value >= HIGH_RISK_THRESHOLD:
        return "high"
    if risk_score_value >= MEDIUM_RISK_THRESHOLD:
        return "medium"
    return "low"
