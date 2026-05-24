from datetime import timedelta
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.vk_oauth import VKUserInfo
from app.core.config import settings
from app.core.security import create_access_token, decode_access_token
from app.db.session import AsyncSessionLocal
from app.main import app
from app.services.auth import AuthService


def _sync_database_url() -> str:
    return settings.sqlalchemy_database_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture(scope="module", autouse=True)
def require_database() -> None:
    try:
        with psycopg.connect(_sync_database_url(), connect_timeout=2) as connection:
            connection.execute("select 1")
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL is not available for auth tests: {exc}")


@pytest.fixture(autouse=True)
def clean_database() -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        connection.execute(
            """
            truncate table
                activity_events,
                employee_metrics,
                schedule_exceptions,
                team_members,
                work_schedules,
                employees,
                teams
            restart identity cascade
            """
        )


class FakeVKOAuthClient:
    def authorization_url(self) -> str:
        return "https://vk.example/authorize"

    async def exchange_code_for_access_token(self, code: str) -> str:
        assert code == "valid-code"
        return "vk-access-token"

    async def get_user_info(self, access_token: str) -> VKUserInfo:
        assert access_token == "vk-access-token"
        return VKUserInfo(vk_user_id="42", full_name="VK User")


def test_create_and_decode_access_token() -> None:
    employee_id = uuid4()
    token = create_access_token(employee_id=employee_id, role="manager")

    payload = decode_access_token(token)

    assert payload.employee_id == employee_id
    assert payload.role == "manager"


def test_decode_invalid_access_token_raises() -> None:
    with pytest.raises(ValueError):
        decode_access_token("not-a-token")


def test_decode_expired_access_token_raises() -> None:
    token = create_access_token(
        employee_id=uuid4(),
        role="employee",
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(ValueError):
        decode_access_token(token)


@pytest.mark.asyncio
async def test_vk_auth_service_creates_employee_and_token() -> None:
    async with AsyncSessionLocal() as session:
        response = await AuthService(session, FakeVKOAuthClient()).authenticate_vk_code(
            "valid-code"
        )

    payload = decode_access_token(response.access_token)
    assert payload.employee_id == response.employee.id
    assert payload.role == "employee"
    assert response.employee.vk_user_id == "42"


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_auth_me_returns_current_employee() -> None:
    employee_id = uuid4()
    with psycopg.connect(_sync_database_url()) as connection:
        connection.execute(
            """
            insert into employees (
                id, vk_user_id, role, full_name, email, timezone, work_format
            )
            values (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                employee_id,
                "100",
                "employee",
                "Current Employee",
                f"current-{uuid4().hex}@example.com",
                "Europe/Moscow",
                "remote",
            ),
        )
    token = create_access_token(employee_id=employee_id, role="employee")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert UUID(response.json()["id"]) == employee_id


@pytest.mark.asyncio
async def test_vk_login_endpoint_returns_authorization_url() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/auth/vk/login")

    assert response.status_code == 200
    assert "authorization_url" in response.json()
