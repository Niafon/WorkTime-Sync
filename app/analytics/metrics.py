from dataclasses import dataclass
from datetime import date, datetime

ACTUALITY_DECAY_DAYS = 90

RISK_ACTUALITY_WEIGHT = 0.30
RISK_CONFLICT_WEIGHT = 0.30
RISK_LOAD_WEIGHT = 0.25
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


def days_since_update(last_updated_at: datetime, today: date) -> int:
    return max(0, (today - last_updated_at.date()).days)


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


def risk_score(
    *,
    actuality_score_value: float,
    conflict_rate_value: float,
    load_level_value: float,
    hr_factor: float,
) -> float:
    return (
        RISK_ACTUALITY_WEIGHT * (1.0 - actuality_score_value)
        + RISK_CONFLICT_WEIGHT * conflict_rate_value
        + RISK_LOAD_WEIGHT * load_level_value
        + RISK_HR_WEIGHT * hr_factor
    )


def risk_level(risk_score_value: float) -> str:
    if risk_score_value >= CRITICAL_RISK_THRESHOLD:
        return "critical"
    if risk_score_value >= HIGH_RISK_THRESHOLD:
        return "high"
    if risk_score_value >= MEDIUM_RISK_THRESHOLD:
        return "medium"
    return "low"
