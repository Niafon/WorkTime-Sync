from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, Field


class ConflictEventResponse(BaseModel):
    id: UUID
    employee_id: UUID
    employee_full_name: str
    team_id: UUID | None = None
    team_name: str | None = None
    title: str
    start_dt: datetime
    end_dt: datetime
    timezone: str
    event_type: str
    source: str
    schedule_start_time: time | None = None
    schedule_end_time: time | None = None


class ConflictListResponse(BaseModel):
    items: list[ConflictEventResponse]
    total: int


class AlternativeWindowResponse(BaseModel):
    start_dt: datetime
    end_dt: datetime
    local_start: datetime
    local_end: datetime
    reason: str


class ProposeRescheduleRequest(BaseModel):
    alternative_start_dt: datetime
    alternative_end_dt: datetime
    note: str | None = Field(default=None, max_length=500)
