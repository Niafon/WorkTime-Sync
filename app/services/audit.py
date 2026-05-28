from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.change_history import ChangeHistory
from app.models.employee import Employee
from app.models.schedule_exception import ScheduleException
from app.models.work_schedule import WorkSchedule
from app.repositories.change_history import ChangeHistoryRepository

ENTITY_WORK_SCHEDULE = "work_schedule"
ENTITY_SCHEDULE_EXCEPTION = "schedule_exception"
ENTITY_EMPLOYEE = "employee"

ACTION_CREATE = "create"
ACTION_UPDATE = "update"
ACTION_DEACTIVATE = "deactivate"
ACTION_DELETE = "delete"


def schedule_to_dict(schedule: WorkSchedule) -> dict[str, Any]:
    return {
        "id": str(schedule.id),
        "employee_id": str(schedule.employee_id),
        "work_days": list(schedule.work_days),
        "start_time": schedule.start_time.isoformat(),
        "end_time": schedule.end_time.isoformat(),
        "timezone": schedule.timezone,
        "work_format": schedule.work_format,
        "last_updated_at": schedule.last_updated_at.isoformat(),
        "is_active": schedule.is_active,
    }


def exception_to_dict(exception: ScheduleException) -> dict[str, Any]:
    return {
        "id": str(exception.id),
        "employee_id": str(exception.employee_id),
        "type": exception.type,
        "start_dt": exception.start_dt.isoformat(),
        "end_dt": exception.end_dt.isoformat(),
        "reason": exception.reason,
    }


def employee_to_dict(employee: Employee) -> dict[str, Any]:
    # password_hash намеренно исключён из аудита
    return {
        "id": str(employee.id),
        "vk_user_id": employee.vk_user_id,
        "role": employee.role,
        "full_name": employee.full_name,
        "email": employee.email,
        "position": employee.position,
        "hire_date": employee.hire_date.isoformat() if employee.hire_date else None,
        "timezone": employee.timezone,
        "work_format": employee.work_format,
    }


async def record_change(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: UUID,
    employee_id: UUID,
    action: str,
    changed_by: UUID,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> ChangeHistory:
    entry = ChangeHistory(
        entity_type=entity_type,
        entity_id=entity_id,
        employee_id=employee_id,
        action=action,
        changed_by=changed_by,
        before=before,
        after=after,
        reason=reason,
    )
    return await ChangeHistoryRepository(session).create(entry)
