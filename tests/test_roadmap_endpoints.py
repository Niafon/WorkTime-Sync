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
    return settings.sqlalchemy_database_url.replace(
        "postgresql+asyncpg://", "postgresql://"
    )


@pytest.fixture(scope="module", autouse=True)
def require_database() -> None:
    try:
        with psycopg.connect(_sync_database_url(), connect_timeout=2) as connection:
            connection.execute("select 1")
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL is not available for roadmap tests: {exc}")


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


@pytest.fixture
def actor_id(request: pytest.FixtureRequest) -> Iterator[UUID]:
    """Создаёт admin-актора в БД и подменяет auth, возвращая его id.

    Нужно для тестов где сервер пишет actor.id в FK (created_by_id).
    """
    marker = request.node.get_closest_marker("auth_role")
    role = marker.args[0] if marker and marker.args else "admin"
    with psycopg.connect(_sync_database_url()) as connection:
        actor = _insert_employee(connection, role=role, full_name=f"Actor {role}")

    async def fake_current_employee() -> SimpleNamespace:
        return SimpleNamespace(id=actor, role=role)

    app.dependency_overrides[get_current_employee] = fake_current_employee
    try:
        yield actor
    finally:
        app.dependency_overrides.pop(get_current_employee, None)


def _insert_employee(
    connection: psycopg.Connection[tuple[object, ...]],
    *,
    role: str = "employee",
    full_name: str = "Roadmap Subject",
) -> UUID:
    employee_id = uuid4()
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
            full_name,
            f"roadmap-{uuid4().hex}@example.com",
            "Europe/Moscow",
            "remote",
        ),
    )
    return employee_id


def _insert_problem_data(
    connection: psycopg.Connection[tuple[object, ...]],
    employee_id: UUID,
) -> None:
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    connection.execute(
        """
        insert into employee_metrics (
            id, employee_id, calculated_at, days_since_update, actuality_score,
            outside_events_count, total_events_count, conflict_rate, load_level,
            risk_score, risk_level
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (uuid4(), employee_id, now, 120, 0.0, 2, 4, 0.5, 1.2, 0.75, "high"),
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


@pytest.mark.asyncio
async def test_get_roadmap_returns_empty_initially(client: AsyncClient) -> None:
    response = await client.get("/api/v1/roadmap")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_generate_roadmap_creates_items_and_is_idempotent(
    client: AsyncClient, actor_id: UUID
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)
        _insert_problem_data(connection, employee_id)

    first = await client.post("/api/v1/roadmap/generate", json={})
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["created"] > 0
    assert first_body["skipped"] == 0
    codes = {item["recommendation_code"] for item in first_body["items"]}
    assert "outdated_schedule" in codes
    assert all(
        item["priority_score"] >= 0 and item["priority_score"] <= 100
        for item in first_body["items"]
    )

    second = await client.post("/api/v1/roadmap/generate", json={})
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["created"] == 0
    assert second_body["skipped"] >= first_body["created"]


@pytest.mark.asyncio
async def test_list_roadmap_with_status_filter_returns_only_matching(
    client: AsyncClient, actor_id: UUID
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)
        _insert_problem_data(connection, employee_id)

    await client.post("/api/v1/roadmap/generate", json={})

    response = await client.get("/api/v1/roadmap?status=pending")
    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert all(item["status"] == "pending" for item in items)

    empty = await client.get("/api/v1/roadmap?status=completed")
    assert empty.status_code == 200
    assert empty.json()["items"] == []


@pytest.mark.asyncio
async def test_patch_status_requested_sets_timestamp_and_creates_notification(
    client: AsyncClient, actor_id: UUID
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)
        _insert_problem_data(connection, employee_id)

    generated = await client.post("/api/v1/roadmap/generate", json={})
    outdated_items = [
        item
        for item in generated.json()["items"]
        if item["recommendation_code"] == "outdated_schedule"
    ]
    assert outdated_items
    item_id = outdated_items[0]["id"]

    patched = await client.patch(
        f"/api/v1/roadmap/{item_id}/status", json={"status": "requested"}
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["status"] == "requested"
    assert body["requested_at"] is not None
    assert body["confirmation_request_id"] is not None

    # subject is the employee → notification recipient is the employee itself
    notifications = await client.get(
        f"/api/v1/notifications?unread_only=true",
        headers={},
    )
    # current user via fixture is admin (uuid4 random) — нет нотификаций для admin'а
    assert notifications.status_code == 200

    with psycopg.connect(_sync_database_url()) as connection:
        notif_count = connection.execute(
            "select count(*) from notifications where recipient_id = %s",
            (employee_id,),
        ).fetchone()
        assert notif_count is not None and notif_count[0] == 1


@pytest.mark.asyncio
async def test_patch_status_invalid_transition_returns_400(
    client: AsyncClient, actor_id: UUID
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)
        _insert_problem_data(connection, employee_id)

    generated = await client.post("/api/v1/roadmap/generate", json={})
    item_id = generated.json()["items"][0]["id"]

    response = await client.patch(
        f"/api/v1/roadmap/{item_id}/status", json={"status": "acknowledged"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_delete_roadmap_item_marks_as_dismissed(
    client: AsyncClient, actor_id: UUID
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)
        _insert_problem_data(connection, employee_id)

    generated = await client.post("/api/v1/roadmap/generate", json={})
    item_id = generated.json()["items"][0]["id"]

    response = await client.delete(f"/api/v1/roadmap/{item_id}")
    assert response.status_code == 204

    fetched = await client.get(f"/api/v1/roadmap/{item_id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "dismissed"


@pytest.mark.asyncio
async def test_generate_after_completed_recreates_item(
    client: AsyncClient, actor_id: UUID
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)
        _insert_problem_data(connection, employee_id)

    generated = await client.post("/api/v1/roadmap/generate", json={})
    outdated_items = [
        item
        for item in generated.json()["items"]
        if item["recommendation_code"] == "outdated_schedule"
    ]
    assert outdated_items
    item_id = outdated_items[0]["id"]

    await client.patch(
        f"/api/v1/roadmap/{item_id}/status", json={"status": "completed"}
    )

    regenerated = await client.post("/api/v1/roadmap/generate", json={})
    assert regenerated.status_code == 200
    recreated = [
        item
        for item in regenerated.json()["items"]
        if item["recommendation_code"] == "outdated_schedule"
    ]
    assert recreated  # new item created because previous one is completed


@pytest.mark.asyncio
@pytest.mark.auth_role("employee")
async def test_generate_requires_planner_role(client: AsyncClient) -> None:
    response = await client.post("/api/v1/roadmap/generate", json={})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_notifications_list_for_recipient(client: AsyncClient) -> None:
    response = await client.get("/api/v1/notifications")
    assert response.status_code == 200
    assert response.json() == []
