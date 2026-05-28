from datetime import date, datetime, time
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.core.employment import EmploymentType
from app.core.roles import EmployeeRole
from app.models.employee import Employee
from app.models.schedule_confirmation_request import CONFIRMATION_STATUS_PENDING
from app.schemas.employee_metric import EmployeeMetricResponse


def _validate_timezone_name(value: str) -> str:
    try:
        ZoneInfo(value)
    except (KeyError, ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError(
            f"unknown timezone {value!r}; expected IANA name like 'Europe/Moscow'"
        ) from exc
    return value

TIMEZONE_CITY_LABELS_RU: dict[str, str] = {
    "Europe/Moscow": "Москва",
    "Europe/Kaliningrad": "Калининград",
    "Europe/Samara": "Самара",
    "Europe/London": "Лондон",
    "Europe/Berlin": "Берлин",
    "Europe/Istanbul": "Стамбул",
    "Asia/Yekaterinburg": "Екатеринбург",
    "Asia/Omsk": "Омск",
    "Asia/Krasnoyarsk": "Красноярск",
    "Asia/Novosibirsk": "Новосибирск",
    "Asia/Irkutsk": "Иркутск",
    "Asia/Yakutsk": "Якутск",
    "Asia/Vladivostok": "Владивосток",
    "Asia/Magadan": "Магадан",
    "Asia/Kamchatka": "Камчатка",
    "UTC": "UTC",
}


def _build_timezone_label(tz_name: str, reference_at: datetime) -> str:
    """Формат: 'UTC+3 Москва' / 'UTC+5 Екатеринбург' / 'UTC' для неизвестных.

    Если tz_name не известен системе (например пришёл "Moscow" вместо
    "Europe/Moscow" из плохого импорта) — возвращаем только city, не маскируя
    другие баги бэка, как делал прежний `except Exception`.
    """
    city = TIMEZONE_CITY_LABELS_RU.get(tz_name, tz_name.split("/")[-1].replace("_", " "))
    try:
        offset = ZoneInfo(tz_name).utcoffset(reference_at)
    except (KeyError, ValueError, ZoneInfoNotFoundError):
        return city
    if offset is None:
        return city
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    abs_minutes = abs(total_minutes)
    hours, minutes = divmod(abs_minutes, 60)
    suffix = f"{sign}{hours}" if minutes == 0 else f"{sign}{hours}:{minutes:02d}"
    return f"UTC{suffix} {city}"


class EmployeeCreate(BaseModel):
    vk_user_id: str | None = None
    role: EmployeeRole
    full_name: str
    email: EmailStr | None = None
    position: str | None = None
    hire_date: date | None = None
    timezone: str
    work_format: str
    employment_type: EmploymentType = EmploymentType.FULL_TIME

    _check_tz = field_validator("timezone")(lambda cls, v: _validate_timezone_name(v))


class EmployeeUpdate(BaseModel):
    vk_user_id: str | None = None
    role: EmployeeRole | None = None
    full_name: str | None = None
    email: EmailStr | None = None
    position: str | None = None
    hire_date: date | None = None
    timezone: str | None = None
    work_format: str | None = None
    employment_type: EmploymentType | None = None

    @field_validator("timezone")
    @classmethod
    def _check_tz(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_timezone_name(value)


class EmployeeResponse(BaseModel):
    id: UUID
    vk_user_id: str | None
    role: EmployeeRole
    full_name: str
    email: EmailStr | None
    position: str | None
    hire_date: date | None
    timezone: str
    work_format: str
    employment_type: EmploymentType
    created_at: datetime
    updated_at: datetime
    team_ids: list[UUID] = []
    metric: EmployeeMetricResponse | None = None
    timezone_label: str | None = None
    has_pending_confirmation: bool = False

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_employee(cls, employee: Employee) -> "EmployeeResponse":
        """Сериализация с подтянутыми relations (metrics, team_members, confirmation_requests).

        Подразумевает, что relations уже подгружены selectinload-ом, иначе
        async-сессия не сможет лениво их загрузить и упадёт.
        """
        metric = (
            EmployeeMetricResponse.model_validate(employee.metrics)
            if employee.metrics is not None
            else None
        )
        has_pending = any(
            req.status == CONFIRMATION_STATUS_PENDING for req in employee.confirmation_requests
        )
        return cls(
            id=employee.id,
            vk_user_id=employee.vk_user_id,
            role=employee.role,
            full_name=employee.full_name,
            email=employee.email,
            position=employee.position,
            hire_date=employee.hire_date,
            timezone=employee.timezone,
            work_format=employee.work_format,
            employment_type=EmploymentType(employee.employment_type),
            created_at=employee.created_at,
            updated_at=employee.updated_at,
            team_ids=[member.team_id for member in employee.team_members],
            metric=metric,
            timezone_label=_build_timezone_label(employee.timezone, employee.updated_at),
            has_pending_confirmation=has_pending,
        )


class EmployeeFullScheduleInput(BaseModel):
    work_days: list[int]
    start_time: time
    end_time: time
    timezone: str

    _check_tz = field_validator("timezone")(lambda cls, v: _validate_timezone_name(v))


class EmployeeFullTeamInput(BaseModel):
    team_id: UUID
    role_in_team: Literal["lead", "pm", "analyst", "member"]


class EmployeeFullCreate(BaseModel):
    vk_user_id: str | None = None
    role: EmployeeRole
    full_name: str
    email: EmailStr | None = None
    position: str | None = None
    hire_date: date | None = None
    employment_type: EmploymentType
    timezone: str
    work_format: Literal["office", "remote", "hybrid"]
    schedule: EmployeeFullScheduleInput
    team: EmployeeFullTeamInput | None = None

    _check_tz = field_validator("timezone")(lambda cls, v: _validate_timezone_name(v))
