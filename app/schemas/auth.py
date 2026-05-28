from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.roles import EmployeeRole
from app.models.employee import Employee


class VKLoginResponse(BaseModel):
    authorization_url: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255, alias="fullName")


class UserResponse(BaseModel):
    """Профиль пользователя в формате, который ожидает фронт (camelCase)."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    # VK-юзеры могут не иметь email — оставляем optional.
    email: EmailStr | None = None
    full_name: str = Field(alias="fullName", serialization_alias="fullName")
    role: EmployeeRole
    initials: str

    @classmethod
    def from_employee(cls, employee: Employee) -> "UserResponse":
        return cls(
            id=employee.id,
            email=employee.email,
            full_name=employee.full_name,
            role=employee.role,
            initials=_build_initials(employee.full_name),
        )


class AuthResponse(BaseModel):
    """Ответ на login/register: формат, который ожидает фронт."""

    token: str
    user: UserResponse


def _build_initials(full_name: str) -> str:
    parts = [chunk for chunk in full_name.strip().split() if chunk]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()
