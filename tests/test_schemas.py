from datetime import UTC, datetime, time
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import EmployeeCreate, EmployeeResponse, WorkScheduleCreate


def test_employee_response_validates_from_attributes() -> None:
    employee_id = uuid4()
    created_at = datetime.now(UTC)
    source = SimpleNamespace(
        id=employee_id,
        vk_user_id="123",
        role="employee",
        full_name="Ada Lovelace",
        email="ada@example.com",
        position="Engineer",
        timezone="Europe/Moscow",
        work_format="remote",
        created_at=created_at,
        updated_at=created_at,
    )

    schema = EmployeeResponse.model_validate(source)

    assert schema.id == employee_id
    assert schema.email == "ada@example.com"


def test_employee_create_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        EmployeeCreate(
            role="employee",
            full_name="Ada Lovelace",
            email="not-an-email",
            timezone="Europe/Moscow",
            work_format="remote",
        )


def test_work_schedule_create_uses_uuid_time_and_work_day_list() -> None:
    employee_id = uuid4()
    last_updated_at = datetime.now(UTC)

    schema = WorkScheduleCreate(
        employee_id=employee_id,
        work_days=[0, 1, 2, 3, 4],
        start_time=time(9, 0),
        end_time=time(18, 0),
        timezone="Europe/Moscow",
        last_updated_at=last_updated_at,
        is_active=True,
    )

    assert schema.employee_id == employee_id
    assert schema.work_days == [0, 1, 2, 3, 4]
