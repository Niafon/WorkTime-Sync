from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ExceptionType = Literal["vacation", "sick_leave", "business_trip", "personal_hours"]


class ScheduleExceptionCreate(BaseModel):
    employee_id: UUID
    type: ExceptionType
    start_dt: datetime
    end_dt: datetime
    reason: str | None = None


class ScheduleExceptionUpdate(BaseModel):
    type: ExceptionType | None = None
    start_dt: datetime | None = None
    end_dt: datetime | None = None
    reason: str | None = None


class ScheduleExceptionResponse(BaseModel):
    id: UUID
    employee_id: UUID
    type: str
    start_dt: datetime
    end_dt: datetime
    reason: str | None

    model_config = ConfigDict(from_attributes=True)
