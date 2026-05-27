from datetime import UTC, datetime
from uuid import UUID, uuid4

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
        pytest.skip(f"PostgreSQL is not available for snapshot tests: {exc}")


@pytest.fixture(autouse=True)
def clean_database() -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        connection.execute(
            """
            truncate table
                employee_metric_snapshots,
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


def _insert_employee(connection: psycopg.Connection, employee_id: UUID) -> None:
    connection.execute(
        """
        insert into employees (id, role, full_name, email, timezone, work_format, created_at)
        values (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            employee_id,
            "employee",
            "Snapshot Subject",
            f"snap-{uuid4().hex}@example.com",
            "Europe/Moscow",
            "remote",
            datetime(2026, 1, 1, tzinfo=UTC),
        ),
    )


def _snapshot_count(employee_id: UUID) -> int:
    with psycopg.connect(_sync_database_url()) as connection:
        row = connection.execute(
            "select count(*) from employee_metric_snapshots where employee_id = %s",
            (employee_id,),
        ).fetchone()
    return int(row[0])


def _metric_count(employee_id: UUID) -> int:
    with psycopg.connect(_sync_database_url()) as connection:
        row = connection.execute(
            "select count(*) from employee_metrics where employee_id = %s",
            (employee_id,),
        ).fetchone()
    return int(row[0])


@pytest.mark.asyncio
async def test_recompute_metrics_writes_snapshot(client: AsyncClient) -> None:
    employee_id = uuid4()
    with psycopg.connect(_sync_database_url()) as connection:
        _insert_employee(connection, employee_id)

    response = await client.post("/api/v1/admin/recompute-metrics?window_days=14")

    assert response.status_code == 200
    assert response.json()["processed_count"] == 1
    assert _snapshot_count(employee_id) == 1


@pytest.mark.asyncio
async def test_two_recomputes_keep_one_metric_but_append_snapshots(client: AsyncClient) -> None:
    employee_id = uuid4()
    with psycopg.connect(_sync_database_url()) as connection:
        _insert_employee(connection, employee_id)

    await client.post("/api/v1/admin/recompute-metrics?window_days=14")
    await client.post("/api/v1/admin/recompute-metrics?window_days=14")

    assert _metric_count(employee_id) == 1
    assert _snapshot_count(employee_id) == 2


@pytest.mark.asyncio
async def test_recompute_all_shares_taken_at_across_employees(client: AsyncClient) -> None:
    employees = [uuid4(), uuid4(), uuid4()]
    with psycopg.connect(_sync_database_url()) as connection:
        for employee_id in employees:
            _insert_employee(connection, employee_id)

    response = await client.post("/api/v1/admin/recompute-metrics?window_days=7")

    assert response.status_code == 200
    assert response.json()["processed_count"] == 3

    with psycopg.connect(_sync_database_url()) as connection:
        rows = connection.execute(
            "select distinct taken_at from employee_metric_snapshots"
        ).fetchall()
    assert len(rows) == 1
