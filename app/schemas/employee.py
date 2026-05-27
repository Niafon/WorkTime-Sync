from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, EmailStr

from app.core.roles import EmployeeRole
from app.models.employee import Employee
from app.schemas.employee_metric import EmployeeMetricResponse

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
    """Формат: 'UTC+3 Москва' / 'UTC+5 Екатеринбург' / 'UTC' для неизвестных."""
    city = TIMEZONE_CITY_LABELS_RU.get(tz_name, tz_name.split("/")[-1].replace("_", " "))
    try:
        offset = ZoneInfo(tz_name).utcoffset(reference_at)
    except Exception:
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
    timezone: str
    work_format: str


class EmployeeUpdate(BaseModel):
    vk_user_id: str | None = None
    role: EmployeeRole | None = None
    full_name: str | None = None
    email: EmailStr | None = None
    position: str | None = None
    timezone: str | None = None
    work_format: str | None = None


class EmployeeResponse(BaseModel):
    id: UUID
    vk_user_id: str | None
    role: EmployeeRole
    full_name: str
    email: EmailStr | None
    position: str | None
    timezone: str
    work_format: str
    created_at: datetime
    updated_at: datetime
    team_ids: list[UUID] = []
    metric: EmployeeMetricResponse | None = None
    timezone_label: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_employee(cls, employee: Employee) -> "EmployeeResponse":
        """Сериализация с подтянутыми relations (metrics, team_members).

        Подразумевает, что relations уже подгружены selectinload-ом, иначе
        async-сессия не сможет лениво их загрузить и упадёт.
        """
        metric = (
            EmployeeMetricResponse.model_validate(employee.metrics)
            if employee.metrics is not None
            else None
        )
        return cls(
            id=employee.id,
            vk_user_id=employee.vk_user_id,
            role=employee.role,
            full_name=employee.full_name,
            email=employee.email,
            position=employee.position,
            timezone=employee.timezone,
            work_format=employee.work_format,
            created_at=employee.created_at,
            updated_at=employee.updated_at,
            team_ids=[member.team_id for member in employee.team_members],
            metric=metric,
            timezone_label=_build_timezone_label(employee.timezone, employee.updated_at),
        )
