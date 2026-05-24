from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class EmployeeCreate(BaseModel):
    vk_user_id: str | None = None
    role: str
    full_name: str
    email: EmailStr | None = None
    position: str | None = None
    timezone: str
    work_format: str


class EmployeeUpdate(BaseModel):
    vk_user_id: str | None = None
    role: str | None = None
    full_name: str | None = None
    email: EmailStr | None = None
    position: str | None = None
    timezone: str | None = None
    work_format: str | None = None


class EmployeeResponse(BaseModel):
    id: UUID
    vk_user_id: str | None
    role: str
    full_name: str
    email: EmailStr | None
    position: str | None
    timezone: str
    work_format: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
