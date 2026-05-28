from datetime import datetime
from uuid import UUID

from dateutil.rrule import rrulestr
from pydantic import BaseModel, ConfigDict, field_validator


class ActivityEventCreate(BaseModel):
    employee_id: UUID
    external_id: str | None = None
    source: str
    event_type: str
    title: str
    start_dt: datetime
    end_dt: datetime
    timezone: str
    recurrence_rule: str | None = None
    is_recurring: bool = False
    is_outside_schedule: bool = False

    @field_validator("recurrence_rule")
    @classmethod
    def _validate_recurrence_rule(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        try:
            rrulestr(value, dtstart=datetime(2000, 1, 1))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"invalid recurrence_rule: {exc}") from exc
        return value


class ActivityEventImportResult(BaseModel):
    imported_count: int
    skipped_duplicate_count: int
    errors: list[str]


class ActivityEventResponse(BaseModel):
    id: UUID
    employee_id: UUID
    external_id: str | None
    source: str
    event_type: str
    title: str
    start_dt: datetime
    end_dt: datetime
    timezone: str
    recurrence_rule: str | None
    is_recurring: bool
    is_outside_schedule: bool

    model_config = ConfigDict(from_attributes=True)
