from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ActivityEventCreate(BaseModel):
    employee_id: UUID
    external_id: str | None = None
    source: str
    event_type: str
    title: str
    start_dt: datetime
    end_dt: datetime
    timezone: str
    is_recurring: bool = False
    is_outside_schedule: bool = False


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
    is_recurring: bool
    is_outside_schedule: bool

    model_config = ConfigDict(from_attributes=True)
