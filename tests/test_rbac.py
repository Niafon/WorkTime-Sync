"""RBAC tests: per-endpoint role matrix enforcement.

Все эндпоинты протестированы через FastAPI с override-нутым get_current_employee
(см. tests/conftest.py — маркер @pytest.mark.auth_role("...")). База данных не нужна,
т.к. 403 возвращается раньше любого запроса в БД.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


def _employee_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "role": "employee",
        "full_name": "Test Employee",
        "timezone": "Europe/Moscow",
        "work_format": "remote",
    }
    payload.update(overrides)
    return payload


def _schedule_payload(employee_id: UUID | str) -> dict[str, Any]:
    return {
        "employee_id": str(employee_id),
        "work_days": [0, 1, 2, 3, 4],
        "start_time": "09:00:00",
        "end_time": "18:00:00",
        "timezone": "Europe/Moscow",
    }


def _exception_payload(employee_id: UUID | str) -> dict[str, Any]:
    return {
        "employee_id": str(employee_id),
        "kind": "vacation",
        "starts_at": "2026-06-01T00:00:00+00:00",
        "ends_at": "2026-06-08T00:00:00+00:00",
        "comment": "test",
    }


# ---------- POST /employees ----------


@pytest.mark.asyncio
@pytest.mark.auth_role("analyst")
async def test_create_employee_forbidden_for_analyst(client: AsyncClient) -> None:
    response = await client.post("/api/v1/employees", json=_employee_payload())
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("employee")
async def test_create_employee_forbidden_for_employee(client: AsyncClient) -> None:
    response = await client.post("/api/v1/employees", json=_employee_payload())
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("manager")
async def test_create_employee_forbidden_for_manager(client: AsyncClient) -> None:
    response = await client.post("/api/v1/employees", json=_employee_payload())
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("pm")
async def test_create_employee_forbidden_for_pm(client: AsyncClient) -> None:
    response = await client.post("/api/v1/employees", json=_employee_payload())
    assert response.status_code == 403


# ---------- PATCH /employees/{id} ----------


@pytest.mark.asyncio
@pytest.mark.auth_role("analyst")
async def test_update_employee_forbidden_for_non_self_analyst(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/v1/employees/{uuid4()}",
        json={"position": "Engineer"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("employee")
async def test_update_employee_forbidden_for_other_employee(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/v1/employees/{uuid4()}",
        json={"position": "Engineer"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("hr")
async def test_update_employee_role_change_forbidden_for_hr(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/v1/employees/{uuid4()}",
        json={"role": "admin"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("manager")
async def test_update_employee_role_change_forbidden_for_manager(client: AsyncClient) -> None:
    # manager is not in allowed roles for PATCH at all, except self.
    response = await client.patch(
        f"/api/v1/employees/{uuid4()}",
        json={"role": "admin"},
    )
    assert response.status_code == 403


# ---------- POST /employees/{id}/schedules ----------


@pytest.mark.asyncio
@pytest.mark.auth_role("analyst")
async def test_create_schedule_forbidden_for_analyst(client: AsyncClient) -> None:
    target = uuid4()
    response = await client.post(
        f"/api/v1/employees/{target}/schedules",
        json=_schedule_payload(target),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("employee")
async def test_create_schedule_forbidden_for_other_employee(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/employees/{uuid4()}/schedules",
        json=_schedule_payload(uuid4()),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("pm")
async def test_create_schedule_forbidden_for_pm(client: AsyncClient) -> None:
    target = uuid4()
    response = await client.post(
        f"/api/v1/employees/{target}/schedules",
        json=_schedule_payload(target),
    )
    assert response.status_code == 403


# ---------- POST /employees/{id}/exceptions ----------


@pytest.mark.asyncio
@pytest.mark.auth_role("analyst")
async def test_create_exception_forbidden_for_analyst(client: AsyncClient) -> None:
    target = uuid4()
    response = await client.post(
        f"/api/v1/employees/{target}/exceptions",
        json=_exception_payload(target),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("employee")
async def test_create_exception_forbidden_for_other_employee(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/employees/{uuid4()}/exceptions",
        json=_exception_payload(uuid4()),
    )
    assert response.status_code == 403


# ---------- POST /teams ----------


@pytest.mark.asyncio
@pytest.mark.auth_role("analyst")
async def test_create_team_forbidden_for_analyst(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/teams",
        json={"name": "Team A", "description": "x"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("employee")
async def test_create_team_forbidden_for_employee(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/teams",
        json={"name": "Team A", "description": "x"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("hr")
async def test_create_team_forbidden_for_hr(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/teams",
        json={"name": "Team A", "description": "x"},
    )
    assert response.status_code == 403


# ---------- PATCH /teams/{id} ----------


@pytest.mark.asyncio
@pytest.mark.auth_role("hr")
async def test_update_team_forbidden_for_hr(client: AsyncClient) -> None:
    response = await client.patch(
        f"/api/v1/teams/{uuid4()}",
        json={"description": "new"},
    )
    assert response.status_code == 403


# ---------- /teams/{id}/members POST/DELETE ----------


@pytest.mark.asyncio
@pytest.mark.auth_role("analyst")
async def test_add_team_member_forbidden_for_analyst(client: AsyncClient) -> None:
    team_id = uuid4()
    response = await client.post(
        f"/api/v1/teams/{team_id}/members",
        json={
            "team_id": str(team_id),
            "employee_id": str(uuid4()),
            "role_in_team": "developer",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("employee")
async def test_delete_team_member_forbidden_for_employee(client: AsyncClient) -> None:
    response = await client.delete(f"/api/v1/teams/{uuid4()}/members/{uuid4()}")
    assert response.status_code == 403


# ---------- POST /teams/{id}/meeting-recommendations ----------


@pytest.mark.asyncio
@pytest.mark.auth_role("analyst")
async def test_meeting_recommendations_forbidden_for_analyst(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/teams/{uuid4()}/meeting-recommendations",
        json={
            "start_dt": "2026-06-01T00:00:00+00:00",
            "end_dt": "2026-06-08T00:00:00+00:00",
            "duration_minutes": 60,
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("hr")
async def test_meeting_recommendations_forbidden_for_hr(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/v1/teams/{uuid4()}/meeting-recommendations",
        json={
            "start_dt": "2026-06-01T00:00:00+00:00",
            "end_dt": "2026-06-08T00:00:00+00:00",
            "duration_minutes": 60,
        },
    )
    assert response.status_code == 403


# ---------- POST /import/events/csv|json ----------


@pytest.mark.asyncio
@pytest.mark.auth_role("analyst")
async def test_import_events_csv_forbidden_for_analyst(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/import/events/csv",
        files={"file": ("events.csv", b"col\n1\n", "text/csv")},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("employee")
async def test_import_events_json_forbidden_for_employee(client: AsyncClient) -> None:
    response = await client.post("/api/v1/import/events/json", json=[])
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("manager")
async def test_import_events_json_forbidden_for_manager(client: AsyncClient) -> None:
    response = await client.post("/api/v1/import/events/json", json=[])
    assert response.status_code == 403


# ---------- POST /events/manual ----------


def _manual_event_payload(employee_id: UUID | str) -> dict[str, Any]:
    return {
        "employee_id": str(employee_id),
        "source": "manual",
        "event_type": "meeting",
        "title": "Sync",
        "start_dt": "2026-06-01T12:00:00+00:00",
        "end_dt": "2026-06-01T12:30:00+00:00",
        "timezone": "Europe/Moscow",
    }


@pytest.mark.asyncio
@pytest.mark.auth_role("analyst")
async def test_create_manual_event_forbidden_for_analyst(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/events/manual",
        json=_manual_event_payload(uuid4()),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("employee")
async def test_create_manual_event_forbidden_for_other_employee(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/events/manual",
        json=_manual_event_payload(uuid4()),
    )
    assert response.status_code == 403
