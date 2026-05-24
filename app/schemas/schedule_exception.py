from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ScheduleExceptionCreate(BaseModel):
    employee_id: UUID
    type: str
    start_dt: datetime
    end_dt: datetime
    reason: str | None = None


class ScheduleExceptionResponse(BaseModel):
    id: UUID
    employee_id: UUID
    type: str
    start_dt: datetime
    end_dt: datetime
    reason: str | None

    model_config = ConfigDict(from_attributes=True)
