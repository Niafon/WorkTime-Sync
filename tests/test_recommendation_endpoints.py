from datetime import UTC, datetime, time, timedelta
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
        pytest.skip(f"PostgreSQL is not available for recommendation endpoint tests: {exc}")


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


def _insert_employee(connection: psycopg.Connection[tuple[object, ...]]) -> UUID:
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
            "employee",
            "Recommendation Subject",
            f"recommendation-{uuid4().hex}@example.com",
            "Europe/Moscow",
            "remote",
        ),
    )
    return employee_id


def _insert_team(connection: psycopg.Connection[tuple[object, ...]], employee_id: UUID) -> UUID:
    team_id = uuid4()
    connection.execute("insert into teams (id, name) values (%s, %s)", (team_id, "Team"))
    connection.execute(
        "insert into team_members (team_id, employee_id, role_in_team) values (%s, %s, %s)",
        (team_id, employee_id, "developer"),
    )
    return team_id


def _insert_problem_data(
    connection: psycopg.Connection[tuple[object, ...]],
    employee_id: UUID,
) -> None:
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    connection.execute(
        """
        insert into employee_metrics (
            id,
            employee_id,
            calculated_at,
            days_since_update,
            actuality_score,
            outside_events_count,
            total_events_count,
            conflict_rate,
            load_level,
            risk_score,
            risk_level
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (uuid4(), employee_id, now, 120, 0.0, 2, 4, 0.5, 1.2, 0.75, "high"),
    )
    connection.execute(
        """
        insert into work_schedules (
            id,
            employee_id,
            work_days,
            start_time,
            end_time,
            timezone,
            work_format,
            last_updated_at,
            is_active
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
            id,
            employee_id,
            source,
            event_type,
            title,
            start_dt,
            end_dt,
            timezone,
            is_recurring,
            is_outside_schedule
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
async def test_employee_recommendations_empty_when_no_issues(client: AsyncClient) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)

    response = await client.get(f"/api/v1/employees/{employee_id}/recommendations")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_employee_and_global_recommendations_return_issues(client: AsyncClient) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)
        _insert_problem_data(connection, employee_id)

    employee_response = await client.get(f"/api/v1/employees/{employee_id}/recommendations")
    global_response = await client.get("/api/v1/recommendations")

    assert employee_response.status_code == 200
    codes = {recommendation["code"] for recommendation in employee_response.json()}
    assert {
        "outdated_schedule",
        "high_conflict_rate",
        "high_load_level",
        "high_risk_score",
        "events_outside_schedule",
        "timezone_mismatch_suspicion",
    } <= codes
    assert global_response.status_code == 200
    assert global_response.json() == employee_response.json()


@pytest.mark.asyncio
async def test_team_recommendations_return_member_issues(client: AsyncClient) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        employee_id = _insert_employee(connection)
        team_id = _insert_team(connection, employee_id)
        _insert_problem_data(connection, employee_id)

    response = await client.get(f"/api/v1/teams/{team_id}/recommendations")

    assert response.status_code == 200
    assert {recommendation["subject_id"] for recommendation in response.json()} == {
        str(employee_id)
    }
