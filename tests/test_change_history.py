from collections.abc import AsyncIterator
from datetime import UTC, datetime, time
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_employee
from app.core.config import settings
from app.main import app


def _sync_database_url() -> str:
    return settings.sqlalchemy_database_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture(scope="module", autouse=True)
def require_database() -> None:
    try:
        with psycopg.connect(_sync_database_url(), connect_timeout=2) as connection:
            connection.execute("select 1")
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL is not available for change history tests: {exc}")


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


async def _create_employee(client: AsyncClient, *, full_name: str = "Audit Tester") -> dict:
    suffix = uuid4().hex
    response = await client.post(
        "/api/v1/employees",
        json={
            "vk_user_id": suffix[:12],
            "role": "employee",
            "full_name": full_name,
            "email": f"audit-{suffix}@example.com",
            "position": "Engineer",
            "timezone": "Europe/Moscow",
            "work_format": "remote",
        },
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


@pytest.fixture
async def actor_employee(client: AsyncClient) -> AsyncIterator[dict]:
    """Создаёт реального сотрудника-actor и переключает override на его UUID.

    Без этого FK change_history.changed_by → employees.id ломается, т.к.
    дефолтный override в conftest возвращает случайный UUID, которого нет в БД.
    """
    actor = await _create_employee(client, full_name="Audit Actor")
    actor_id = UUID(actor["id"])

    async def real_current_employee() -> SimpleNamespace:
        return SimpleNamespace(id=actor_id, role="admin")

    app.dependency_overrides[get_current_employee] = real_current_employee
    try:
        yield actor
    finally:
        # Не восстанавливаем дефолт вручную — autouse-фикстура сделает это перед
        # следующим тестом.
        app.dependency_overrides.pop(get_current_employee, None)


def _schedule_payload(employee_id: str, *, is_active: bool = True) -> dict:
    return {
        "employee_id": employee_id,
        "work_days": [0, 1, 2, 3, 4],
        "start_time": time(9, 0).isoformat(),
        "end_time": time(18, 0).isoformat(),
        "timezone": "Europe/Moscow",
        "last_updated_at": datetime.now(UTC).isoformat(),
        "is_active": is_active,
    }


@pytest.mark.asyncio
async def test_schedule_create_records_audit(
    client: AsyncClient, actor_employee: dict
) -> None:
    target = await _create_employee(client, full_name="Schedule Target")
    target_id = str(target["id"])

    create_response = await client.post(
        f"/api/v1/employees/{target_id}/schedules",
        json=_schedule_payload(target_id),
    )
    assert create_response.status_code == 201, create_response.text

    history_response = await client.get(f"/api/v1/employees/{target_id}/schedules/history")
    assert history_response.status_code == 200
    entries = history_response.json()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["entity_type"] == "work_schedule"
    assert entry["action"] == "create"
    assert entry["before"] is None
    assert entry["after"] is not None
    assert entry["after"]["timezone"] == "Europe/Moscow"
    assert entry["after"]["work_days"] == [0, 1, 2, 3, 4]
    assert entry["changed_by"] == actor_employee["id"]


@pytest.mark.asyncio
async def test_schedule_replace_records_deactivate_and_create(
    client: AsyncClient, actor_employee: dict
) -> None:
    target = await _create_employee(client, full_name="Schedule Replace")
    target_id = str(target["id"])

    first = await client.post(
        f"/api/v1/employees/{target_id}/schedules",
        json=_schedule_payload(target_id),
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/employees/{target_id}/schedules",
        json=_schedule_payload(target_id),
    )
    assert second.status_code == 201

    history_response = await client.get(f"/api/v1/employees/{target_id}/schedules/history")
    assert history_response.status_code == 200
    entries = history_response.json()
    actions = [entry["action"] for entry in entries]
    # newest first: create (second), deactivate (first), create (first)
    assert actions == ["create", "deactivate", "create"]

    deactivate_entry = entries[1]
    assert deactivate_entry["before"] is not None
    assert deactivate_entry["before"]["is_active"] is True
    assert deactivate_entry["after"] is not None
    assert deactivate_entry["after"]["is_active"] is False


@pytest.mark.asyncio
async def test_exception_create_records_audit(
    client: AsyncClient, actor_employee: dict
) -> None:
    target = await _create_employee(client, full_name="Exception Target")
    target_id = str(target["id"])
    now_iso = datetime.now(UTC).isoformat()

    exc_response = await client.post(
        f"/api/v1/employees/{target_id}/exceptions",
        json={
            "employee_id": target_id,
            "type": "vacation",
            "start_dt": now_iso,
            "end_dt": now_iso,
            "reason": "annual leave",
        },
    )
    assert exc_response.status_code == 201

    history_response = await client.get(f"/api/v1/employees/{target_id}/exceptions/history")
    assert history_response.status_code == 200
    entries = history_response.json()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["entity_type"] == "schedule_exception"
    assert entry["action"] == "create"
    assert entry["after"]["type"] == "vacation"
    assert entry["after"]["reason"] == "annual leave"


@pytest.mark.asyncio
async def test_employee_patch_records_before_after(
    client: AsyncClient, actor_employee: dict
) -> None:
    target = await _create_employee(client, full_name="Patch Target")
    target_id = str(target["id"])

    patch_response = await client.patch(
        f"/api/v1/employees/{target_id}",
        json={"position": "Senior Engineer"},
    )
    assert patch_response.status_code == 200

    history_response = await client.get(
        f"/api/v1/employees/{target_id}/history",
        params={"entity_type": "employee"},
    )
    assert history_response.status_code == 200
    entries = history_response.json()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["entity_type"] == "employee"
    assert entry["action"] == "update"
    assert entry["before"]["position"] == "Engineer"
    assert entry["after"]["position"] == "Senior Engineer"
    # password_hash намеренно не попадает в снимки
    assert "password_hash" not in entry["before"]
    assert "password_hash" not in entry["after"]


@pytest.mark.asyncio
async def test_history_pagination(client: AsyncClient, actor_employee: dict) -> None:
    target = await _create_employee(client, full_name="Pagination Target")
    target_id = str(target["id"])

    for _ in range(3):
        response = await client.post(
            f"/api/v1/employees/{target_id}/schedules",
            json=_schedule_payload(target_id),
        )
        assert response.status_code == 201

    # 3 creates + 2 deactivates = 5 entries
    full = await client.get(f"/api/v1/employees/{target_id}/schedules/history")
    assert full.status_code == 200
    assert len(full.json()) == 5

    paged = await client.get(
        f"/api/v1/employees/{target_id}/schedules/history",
        params={"skip": 2, "limit": 2},
    )
    assert paged.status_code == 200
    assert len(paged.json()) == 2


@pytest.mark.asyncio
async def test_history_filter_by_entity_type(
    client: AsyncClient, actor_employee: dict
) -> None:
    target = await _create_employee(client, full_name="Filter Target")
    target_id = str(target["id"])
    now_iso = datetime.now(UTC).isoformat()

    await client.post(
        f"/api/v1/employees/{target_id}/schedules",
        json=_schedule_payload(target_id),
    )
    await client.post(
        f"/api/v1/employees/{target_id}/exceptions",
        json={
            "employee_id": target_id,
            "type": "sick",
            "start_dt": now_iso,
            "end_dt": now_iso,
            "reason": None,
        },
    )
    await client.patch(
        f"/api/v1/employees/{target_id}",
        json={"position": "Lead"},
    )

    all_history = await client.get(f"/api/v1/employees/{target_id}/history")
    assert all_history.status_code == 200
    entity_types = {entry["entity_type"] for entry in all_history.json()}
    assert entity_types == {"work_schedule", "schedule_exception", "employee"}

    only_schedule = await client.get(f"/api/v1/employees/{target_id}/schedules/history")
    assert only_schedule.status_code == 200
    assert all(entry["entity_type"] == "work_schedule" for entry in only_schedule.json())


@pytest.mark.asyncio
async def test_history_404_for_unknown_employee(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/employees/{uuid4()}/schedules/history")
    assert response.status_code == 404
