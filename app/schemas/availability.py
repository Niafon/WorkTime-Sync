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
    required_employee_ids: list[UUID] = Field(default_factory=list)
    optional_employee_ids: list[UUID] = Field(default_factory=list)
    load_threshold: float = Field(default=0.8, ge=0.0, le=2.0)


class EmployeeLocalTimeResponse(BaseModel):
    employee_id: UUID
    timezone: str
    local_start: datetime
    local_end: datetime


class MeetingRecommendationResponse(BaseModel):
    start_dt: datetime
    end_dt: datetime
    required_available_ids: list[UUID]
    required_missing_ids: list[UUID]
    optional_available_ids: list[UUID]
    optional_missing_ids: list[UUID]
    overloaded_employee_ids: list[UUID]
    local_times: list[EmployeeLocalTimeResponse]
    available_employee_ids: list[UUID]
    unavailable_employee_ids: list[UUID]
    score: float
