from datetime import timedelta
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.vk_oauth import VKUserInfo
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
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
                refresh_tokens,
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
    # CSRF-защита (HMAC-state) добавлена в authenticate_vk_code — берём
    # подписанный state через тот же модуль, который его и проверяет.
    from app.auth.vk_oauth import build_vk_oauth_state

    state = build_vk_oauth_state()
    async with AsyncSessionLocal() as session:
        issued = await AuthService(session, FakeVKOAuthClient()).authenticate_vk_code(
            "valid-code", state
        )

    access_payload = decode_access_token(issued.response.token)
    assert access_payload.employee_id == issued.response.user.id
    assert access_payload.role == "employee"
    refresh_payload = decode_refresh_token(issued.refresh_token)
    assert refresh_payload.employee_id == issued.response.user.id
    assert refresh_payload.token_type == "refresh"


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


def test_create_and_decode_refresh_token() -> None:
    employee_id = uuid4()
    token, expires_at = create_refresh_token(employee_id=employee_id, jti=uuid4().hex)

    payload = decode_refresh_token(token)

    assert payload.employee_id == employee_id
    assert payload.token_type == "refresh"
    # expires_at должен совпадать с exp в payload (с точностью до секунды)
    assert abs((payload.exp - expires_at).total_seconds()) < 1


def test_decode_refresh_token_rejects_access_token() -> None:
    access = create_access_token(employee_id=uuid4(), role="employee")
    with pytest.raises(ValueError):
        decode_refresh_token(access)


def test_decode_access_token_rejects_refresh_token() -> None:
    refresh, _ = create_refresh_token(employee_id=uuid4(), jti=uuid4().hex)
    with pytest.raises(ValueError):
        decode_access_token(refresh)


def test_decode_expired_refresh_token_raises() -> None:
    token, _ = create_refresh_token(
        employee_id=uuid4(),
        jti=uuid4().hex,
        expires_delta=timedelta(seconds=-1),
    )
    with pytest.raises(ValueError):
        decode_refresh_token(token)


def _insert_employee(employee_id: UUID, *, role: str = "employee") -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        connection.execute(
            """
            insert into employees (
                id, role, full_name, email, timezone, work_format
            )
            values (%s, %s, %s, %s, %s, %s)
            """,
            (
                employee_id,
                role,
                "Test Employee",
                f"refresh-{uuid4().hex}@example.com",
                "Europe/Moscow",
                "remote",
            ),
        )


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_login_sets_refresh_cookie() -> None:
    # Регистрируем юзера, потом логинимся и проверяем Set-Cookie.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"login-{uuid4().hex}@example.com"
        reg = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "secret-pass", "fullName": "Tester"},
        )
        assert reg.status_code == 201, reg.text
        assert settings.refresh_cookie_name in reg.cookies
        # Refresh-cookie должна быть валидным refresh-JWT.
        cookie_value = reg.cookies[settings.refresh_cookie_name]
        payload = decode_refresh_token(cookie_value)
        assert payload.token_type == "refresh"


async def _register_and_get_cookie(client: AsyncClient) -> tuple[str, str]:
    """Регистрирует юзера через /auth/register, возвращает (refresh_cookie, employee_id)."""
    email = f"refresh-{uuid4().hex}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secret-pass", "fullName": "Refresh User"},
    )
    assert reg.status_code == 201, reg.text
    cookie = reg.cookies[settings.refresh_cookie_name]
    employee_id = reg.json()["user"]["id"]
    return cookie, employee_id


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_refresh_endpoint_returns_new_access_and_rotates_cookie() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        old_cookie, employee_id = await _register_and_get_cookie(client)
        client.cookies.set(settings.refresh_cookie_name, old_cookie)
        response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 200, response.text
    data = response.json()
    new_access_payload = decode_access_token(data["token"])
    assert str(new_access_payload.employee_id) == employee_id
    # Refresh-cookie должен ротироваться: новый отличается от старого.
    new_cookie = response.cookies[settings.refresh_cookie_name]
    assert new_cookie != old_cookie


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_refresh_endpoint_detects_reuse() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        old_cookie, _ = await _register_and_get_cookie(client)
        # Первый refresh — успешный, ротирует cookie.
        client.cookies.set(settings.refresh_cookie_name, old_cookie)
        first = await client.post("/api/v1/auth/refresh")
        assert first.status_code == 200
        # Повторно используем уже отозванный refresh — reuse detected.
        client.cookies.set(settings.refresh_cookie_name, old_cookie)
        second = await client.post("/api/v1/auth/refresh")
        assert second.status_code == 401
        assert "reuse" in second.json()["detail"].lower()


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_refresh_endpoint_401_without_cookie() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_refresh_endpoint_401_on_invalid_cookie() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={settings.refresh_cookie_name: "not-a-jwt"},
    ) as client:
        response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    # При невалидной cookie бэк должен очистить cookie.
    set_cookie = response.headers.get("set-cookie", "")
    assert settings.refresh_cookie_name in set_cookie


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_refresh_endpoint_401_on_expired_cookie() -> None:
    employee_id = uuid4()
    _insert_employee(employee_id)
    expired_refresh, _ = create_refresh_token(
        employee_id=employee_id,
        jti=uuid4().hex,
        expires_delta=timedelta(seconds=-1),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={settings.refresh_cookie_name: expired_refresh},
    ) as client:
        response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_refresh_endpoint_401_for_deleted_employee() -> None:
    refresh_token, _ = create_refresh_token(
        employee_id=uuid4(),  # never inserted
        jti=uuid4().hex,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={settings.refresh_cookie_name: refresh_token},
    ) as client:
        response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401


@pytest.mark.no_auth_override
@pytest.mark.asyncio
async def test_logout_clears_refresh_cookie() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    set_cookie = response.headers.get("set-cookie", "")
    assert settings.refresh_cookie_name in set_cookie
    # delete_cookie выставляет Max-Age=0 (или прошлую дату).
    assert "max-age=0" in set_cookie.lower() or "expires=" in set_cookie.lower()
