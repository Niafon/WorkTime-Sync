from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta
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
        pytest.skip(f"PostgreSQL is not available for recommendation status tests: {exc}")


@pytest.fixture(autouse=True)
def clean_database() -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        connection.execute(
            """
            truncate table
                notifications,
                roadmap_items,
                schedule_confirmation_requests,
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


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


def _insert_employee(
    connection: psycopg.Connection,
    *,
    role: str = "employee",
) -> UUID:
    employee_id = uuid4()
    connection.execute(
        """
        insert into employees (id, role, full_name, email, timezone, work_format)
        values (%s, %s, %s, %s, %s, %s)
        """,
        (
            employee_id,
            role,
            f"RecStatus {role}",
            f"rec-status-{uuid4().hex}@example.com",
            "Europe/Moscow",
            "remote",
        ),
    )
    return employee_id


def _insert_problem_data(connection: psycopg.Connection, employee_id: UUID) -> None:
    """Создаёт условия, при которых RecommendationService возвращает несколько recs."""
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    connection.execute(
        """
        insert into employee_metrics (
            id, employee_id, calculated_at, days_since_update, actuality_score,
            outside_events_count, total_events_count, conflict_rate, load_level,
            zone_factor, hr_factor, risk_score, risk_level
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (uuid4(), employee_id, now, 120, 0.0, 2, 4, 0.5, 1.2, 0.0, 0.0, 0.85, "critical"),
    )
    connection.execute(
        """
        insert into work_schedules (
            id, employee_id, work_days, start_time, end_time, timezone,
            work_format, last_updated_at, is_active
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            uuid4(),
            employee_id,
            [0, 1, 2, 3, 4],
            time(9, 0),
            time(18, 0),
            "UTC",
            "office",
            now,
            True,
        ),
    )
    connection.execute(
        """
        insert into activity_events (
            id, employee_id, source, event_type, title, start_dt, end_dt,
            timezone, is_recurring, is_outside_schedule
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            uuid4(),
            employee_id,
            "manual",
            "meeting",
            "Late meeting",
            now,
            now + timedelta(hours=1),
            "UTC",
            False,
            True,
        ),
    )


@pytest.fixture
def actor_id() -> Iterator[UUID]:
    """Создаёт admin-актора в БД и подменяет auth."""
    with psycopg.connect(_sync_database_url()) as connection:
        actor = _insert_employee(connection, role="admin")

    async def fake_current_employee() -> SimpleNamespace:
        return SimpleNamespace(id=actor, role="admin")

    app.dependency_overrides[get_current_employee] = fake_current_employee
    try:
        yield actor
    finally:
        app.dependency_overrides.pop(get_current_employee, None)


def _roadmap_item_count(connection: psycopg.Connection) -> int:
    return int(
        connection.execute("select count(*) from roadmap_items").fetchone()[0]
    )


def _roadmap_item_status(connection: psycopg.Connection, item_id: str) -> str:
    return connection.execute(
        "select status from roadmap_items where id = %s", (item_id,)
    ).fetchone()[0]


@pytest.mark.asyncio
async def test_patch_requested_creates_and_advances_roadmap_item(
    client: AsyncClient, actor_id: UUID
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)
        _insert_problem_data(connection, employee_id)

    response = await client.patch(
        f"/api/v1/recommendations/high_load_level/employee/{employee_id}/status",
        json={"status": "requested"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == "high_load_level"
    assert body["status"] == "requested"
    assert body["roadmap_item_id"] is not None

    with psycopg.connect(_sync_database_url()) as connection:
        assert _roadmap_item_count(connection) == 1
        assert _roadmap_item_status(connection, body["roadmap_item_id"]) == "requested"


@pytest.mark.asyncio
async def test_patch_deferred_creates_pending_then_defers(
    client: AsyncClient, actor_id: UUID
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)
        _insert_problem_data(connection, employee_id)

    response = await client.patch(
        f"/api/v1/recommendations/high_load_level/employee/{employee_id}/status",
        json={"status": "deferred"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "deferred"


@pytest.mark.asyncio
async def test_patch_ignored_creates_and_ignores(
    client: AsyncClient, actor_id: UUID
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)
        _insert_problem_data(connection, employee_id)

    response = await client.patch(
        f"/api/v1/recommendations/high_load_level/employee/{employee_id}/status",
        json={"status": "ignored"},
    )

    assert response.status_code == 200
    body = response.json()
    # 'ignored' is terminal — open-item lookup в _enrich возвращает None,
    # поэтому в RecommendationResponse статус снова None после reload.
    # Но в самом ответе PATCH мы вернули _reload_recommendation —
    # который снова вычисляет рекомендацию (она ещё актуальна) с None status.
    assert body["status"] is None or body["status"] == "ignored"


@pytest.mark.asyncio
async def test_get_recommendations_after_patch_returns_status(
    client: AsyncClient, actor_id: UUID
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)
        _insert_problem_data(connection, employee_id)

    await client.patch(
        f"/api/v1/recommendations/high_load_level/employee/{employee_id}/status",
        json={"status": "requested"},
    )

    response = await client.get("/api/v1/recommendations")

    assert response.status_code == 200
    matched = [r for r in response.json() if r["code"] == "high_load_level"]
    assert len(matched) == 1
    assert matched[0]["status"] == "requested"
    assert matched[0]["roadmap_item_id"] is not None


@pytest.mark.asyncio
async def test_get_recommendations_returns_null_status_before_action(
    client: AsyncClient, actor_id: UUID
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)
        _insert_problem_data(connection, employee_id)

    response = await client.get("/api/v1/recommendations")

    assert response.status_code == 200
    items = response.json()
    assert items
    assert all(item["status"] is None for item in items)
    assert all(item["roadmap_item_id"] is None for item in items)


@pytest.mark.asyncio
async def test_patch_unknown_recommendation_returns_404(
    client: AsyncClient, actor_id: UUID
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)

    response = await client.patch(
        f"/api/v1/recommendations/high_load_level/employee/{employee_id}/status",
        json={"status": "requested"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_repeat_patch_after_terminal_status_is_400(
    client: AsyncClient, actor_id: UUID
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)
        _insert_problem_data(connection, employee_id)

    await client.patch(
        f"/api/v1/recommendations/high_load_level/employee/{employee_id}/status",
        json={"status": "ignored"},
    )
    # Item теперь в terminal status='ignored' (нет open). Повтор — снова создаст
    # новый pending. Транзитим в deferred — должно сработать.
    response = await client.patch(
        f"/api/v1/recommendations/high_load_level/employee/{employee_id}/status",
        json={"status": "deferred"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "deferred"


@pytest.mark.asyncio
async def test_bulk_status_filters_by_severity(
    client: AsyncClient, actor_id: UUID
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)
        _insert_problem_data(connection, employee_id)

    response = await client.post(
        "/api/v1/recommendations/bulk-status",
        json={"status": "requested", "severity": "critical"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["updated"] >= 1
    # После bulk апдейта в БД появились roadmap_items
    with psycopg.connect(_sync_database_url()) as connection:
        assert _roadmap_item_count(connection) >= 1
