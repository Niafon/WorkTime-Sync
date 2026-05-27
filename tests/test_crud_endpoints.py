from datetime import UTC, datetime, time
from uuid import uuid4

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient

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
        pytest.skip(f"PostgreSQL is not available for CRUD endpoint tests: {exc}")


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


async def _create_employee(client: AsyncClient) -> dict[str, object]:
    suffix = uuid4().hex
    response = await client.post(
        "/api/v1/employees",
        json={
            "vk_user_id": suffix[:12],
            "role": "employee",
            "full_name": "Ada Lovelace",
            "email": f"ada-{suffix}@example.com",
            "position": "Engineer",
            "timezone": "Europe/Moscow",
            "work_format": "remote",
        },
    )
    assert response.status_code == 201
    return dict(response.json())


async def _create_team(client: AsyncClient) -> dict[str, object]:
    response = await client.post(
        "/api/v1/teams",
        json={"name": f"Platform {uuid4().hex[:8]}", "description": "MVP team"},
    )
    assert response.status_code == 201
    return dict(response.json())


@pytest.mark.asyncio
async def test_employee_create_list_get_and_patch(client: AsyncClient) -> None:
    employee = await _create_employee(client)
    employee_id = employee["id"]

    list_response = await client.get("/api/v1/employees")
    assert list_response.status_code == 200
    assert any(item["id"] == employee_id for item in list_response.json())

    get_response = await client.get(f"/api/v1/employees/{employee_id}")
    assert get_response.status_code == 200
    assert get_response.json()["full_name"] == "Ada Lovelace"

    patch_response = await client.patch(
        f"/api/v1/employees/{employee_id}",
        json={"position": "Senior Engineer"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["position"] == "Senior Engineer"


@pytest.mark.asyncio
async def test_team_create_list_get_patch_and_member_lifecycle(client: AsyncClient) -> None:
    employee = await _create_employee(client)
    team = await _create_team(client)

    list_response = await client.get("/api/v1/teams")
    assert list_response.status_code == 200
    assert any(item["id"] == team["id"] for item in list_response.json())

    patch_response = await client.patch(f"/api/v1/teams/{team['id']}", json={"description": "Core"})
    assert patch_response.status_code == 200
    assert patch_response.json()["description"] == "Core"

    member_response = await client.post(
        f"/api/v1/teams/{team['id']}/members",
        json={
            "team_id": team["id"],
            "employee_id": employee["id"],
            "role_in_team": "developer",
        },
    )
    assert member_response.status_code == 201
    assert member_response.json()["employee_id"] == employee["id"]

    delete_response = await client.delete(f"/api/v1/teams/{team['id']}/members/{employee['id']}")
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_schedule_and_exception_create_read_paths(client: AsyncClient) -> None:
    employee = await _create_employee(client)
    employee_id = str(employee["id"])
    now = datetime.now(UTC)

    schedule_response = await client.post(
        f"/api/v1/employees/{employee_id}/schedules",
        json={
            "employee_id": employee_id,
            "work_days": [0, 1, 2, 3, 4],
            "start_time": time(9, 0).isoformat(),
            "end_time": time(18, 0).isoformat(),
            "timezone": "Europe/Moscow",
            "last_updated_at": now.isoformat(),
            "is_active": True,
        },
    )
    assert schedule_response.status_code == 201

    active_response = await client.get(f"/api/v1/employees/{employee_id}/schedules/active")
    assert active_response.status_code == 200
    assert active_response.json()["employee_id"] == employee_id

    exception_response = await client.post(
        f"/api/v1/employees/{employee_id}/exceptions",
        json={
            "employee_id": employee_id,
            "type": "vacation",
            "start_dt": now.isoformat(),
            "end_dt": now.isoformat(),
            "reason": "planned",
        },
    )
    assert exception_response.status_code == 201

    list_response = await client.get(f"/api/v1/employees/{employee_id}/exceptions")
    assert list_response.status_code == 200
    assert any(item["id"] == exception_response.json()["id"] for item in list_response.json())


@pytest.mark.asyncio
async def test_missing_employee_returns_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/employees/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "employee not found"}


@pytest.mark.asyncio
async def test_delete_team_returns_204_and_cascades_members(
    client: AsyncClient,
) -> None:
    employee = await _create_employee(client)
    team = await _create_team(client)
    member_response = await client.post(
        f"/api/v1/teams/{team['id']}/members",
        json={
            "team_id": team["id"],
            "employee_id": employee["id"],
            "role_in_team": "developer",
        },
    )
    assert member_response.status_code == 201

    delete_response = await client.delete(f"/api/v1/teams/{team['id']}")
    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/teams/{team['id']}")
    assert get_response.status_code == 404

    # employee остался в системе
    employee_get = await client.get(f"/api/v1/employees/{employee['id']}")
    assert employee_get.status_code == 200


@pytest.mark.asyncio
async def test_delete_team_not_found_returns_404(client: AsyncClient) -> None:
    response = await client.delete(f"/api/v1/teams/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.auth_role("employee")
async def test_delete_team_requires_management_role(client: AsyncClient) -> None:
    team_id = uuid4()
    with psycopg.connect(_sync_database_url()) as connection:
        connection.execute(
            "insert into teams (id, name) values (%s, %s)", (team_id, "RBAC test team")
        )
    response = await client.delete(f"/api/v1/teams/{team_id}")
    assert response.status_code == 403
