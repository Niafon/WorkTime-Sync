from datetime import datetime, time
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

WorkFormat = Literal["office", "remote", "hybrid"]

_VALID_WEEKDAYS = frozenset(range(7))  # 0=Mon … 6=Sun


def _validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (KeyError, ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError(
            f"unknown timezone {value!r}; expected IANA name like 'Europe/Moscow'"
        ) from exc
    return value


def _validate_work_days(value: list[int]) -> list[int]:
    if not value:
        raise ValueError("work_days must contain at least one day")
    bad = sorted(set(value) - _VALID_WEEKDAYS)
    if bad:
        raise ValueError(
            f"work_days must contain integers 0..6 (got out-of-range: {bad})"
        )
    # dedup + sort, чтобы downstream-аналитика не зависела от порядка/дублей
    return sorted(set(value))


class WorkScheduleCreate(BaseModel):
    employee_id: UUID
    work_days: list[int]
    start_time: time
    end_time: time
    timezone: str
    work_format: WorkFormat
    last_updated_at: datetime
    is_active: bool

    _validate_tz = field_validator("timezone")(lambda cls, v: _validate_timezone(v))
    _validate_days = field_validator("work_days")(lambda cls, v: _validate_work_days(v))

    @model_validator(mode="after")
    def _check_time_window(self) -> "WorkScheduleCreate":
        # Поддерживаем ночные смены через полночь (start_time > end_time) —
        # это нормальная конфигурация для сменных графиков. Запрещаем только
        # пустое окно start == end (нулевая длительность).
        if self.start_time == self.end_time:
            raise ValueError("start_time and end_time must differ")
        return self


class WorkScheduleResponse(BaseModel):
    id: UUID
    employee_id: UUID
    work_days: list[int]
    start_time: time
    end_time: time
    timezone: str
    work_format: WorkFormat
    last_updated_at: datetime
    confirmed_at: datetime | None = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
