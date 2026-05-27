from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WorkScheduleCreate(BaseModel):
    employee_id: UUID
    work_days: list[int]
    start_time: time
    end_time: time
    timezone: str
    last_updated_at: datetime
    is_active: bool


class WorkScheduleResponse(BaseModel):
    id: UUID
    employee_id: UUID
    work_days: list[int]
    start_time: time
    end_time: time
    timezone: str
    last_updated_at: datetime
    confirmed_at: datetime | None = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
