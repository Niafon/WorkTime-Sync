from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AvailabilityWindowResponse(BaseModel):
    start_dt: datetime
    end_dt: datetime


class EmployeeAvailabilityResponse(BaseModel):
    employee_id: UUID
    timezone: str
    available_windows: list[AvailabilityWindowResponse]


class TeamAvailabilityResponse(BaseModel):
    team_id: UUID
    range_start: datetime
    range_end: datetime
    employees: list[EmployeeAvailabilityResponse]


class MeetingRecommendationRequest(BaseModel):
    start_dt: datetime
    end_dt: datetime
    duration_minutes: int = Field(gt=0, le=480)


class MeetingRecommendationResponse(BaseModel):
    start_dt: datetime
    end_dt: datetime
    available_employee_ids: list[UUID]
    unavailable_employee_ids: list[UUID]
    score: float
