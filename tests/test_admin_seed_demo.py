import psycopg
import pytest
from httpx import ASGITransport, AsyncClient

from app.core import config as config_module
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
        pytest.skip(f"PostgreSQL is not available for seed-demo tests: {exc}")


@pytest.fixture(autouse=True)
def clean_database() -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        connection.execute(
            """
            truncate table
                notifications,
                roadmap_items,
                employee_metric_snapshots,
                activity_events,
                schedule_confirmation_requests,
                schedule_exceptions,
                work_schedules,
                employee_metrics,
                team_members,
                teams,
                employees
            restart identity cascade
            """
        )


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


@pytest.fixture
def debug_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_module.settings, "debug", True)


@pytest.fixture
def debug_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_module.settings, "debug", False)


def _employee_count() -> int:
    with psycopg.connect(_sync_database_url()) as connection:
        row = connection.execute("select count(*) from employees").fetchone()
    return int(row[0])


@pytest.mark.asyncio
async def test_seed_demo_creates_data_when_debug_enabled(
    client: AsyncClient, debug_enabled: None
) -> None:
    response = await client.post(
        "/api/v1/admin/seed-demo",
        json={"small": True, "reset": True, "with_roadmap": True},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["employees_created"] >= 8
    assert body["teams_created"] == 2
    assert body["events_created"] > 0
    assert body["metrics_created"] >= 8
    assert _employee_count() >= 8


@pytest.mark.asyncio
async def test_seed_demo_forbidden_when_debug_disabled(
    client: AsyncClient, debug_disabled: None
) -> None:
    response = await client.post(
        "/api/v1/admin/seed-demo",
        json={"small": True, "reset": True, "with_roadmap": False},
    )
    assert response.status_code == 403
    assert "APP_DEBUG=false" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.auth_role("employee")
async def test_seed_demo_requires_admin_role(
    client: AsyncClient, debug_enabled: None
) -> None:
    response = await client.post(
        "/api/v1/admin/seed-demo",
        json={"small": True, "reset": True, "with_roadmap": False},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_seed_demo_reset_clears_existing(
    client: AsyncClient, debug_enabled: None
) -> None:
    first = await client.post(
        "/api/v1/admin/seed-demo",
        json={"small": True, "reset": True, "with_roadmap": False},
    )
    assert first.status_code == 200
    first_total = _employee_count()

    second = await client.post(
        "/api/v1/admin/seed-demo",
        json={"small": True, "reset": True, "with_roadmap": False},
    )
    assert second.status_code == 200
    second_total = _employee_count()

    assert first_total == second_total
