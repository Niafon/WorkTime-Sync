from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ConfirmationStatus = Literal["pending", "confirmed", "declined"]


class ScheduleConfirmationRequestCreate(BaseModel):
    reason: str | None = None


class ScheduleConfirmDeclineRequest(BaseModel):
    note: str | None = None


class ScheduleConfirmationRequestResponse(BaseModel):
    id: UUID
    employee_id: UUID
    requested_by_id: UUID | None
    requested_by_name: str | None = None
    employee_name: str | None = None
    reason: str | None
    status: ConfirmationStatus
    created_at: datetime
    responded_at: datetime | None
    response_note: str | None

    model_config = ConfigDict(from_attributes=True)


class ScheduleConfirmResponse(BaseModel):
    confirmed_at: datetime
    closed_request_ids: list[UUID]


class BulkScheduleConfirmationRequestCreate(BaseModel):
    employee_ids: list[UUID]
    reason: str | None = None


class BulkScheduleConfirmationRequestResponse(BaseModel):
    created: list[ScheduleConfirmationRequestResponse]
    skipped_employee_ids: list[UUID]
