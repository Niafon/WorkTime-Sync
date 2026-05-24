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
        pytest.skip(f"PostgreSQL is not available for team availability tests: {exc}")


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


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


def _insert_team_with_employee(
    connection: psycopg.Connection[tuple[object, ...]],
    *,
    employee_timezone: str = "UTC",
) -> tuple[UUID, UUID]:
    team_id = uuid4()
    employee_id = uuid4()
    connection.execute("insert into teams (id, name) values (%s, %s)", (team_id, "Availability"))
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
            f"Employee {uuid4().hex[:6]}",
            f"availability-{uuid4().hex}@example.com",
            employee_timezone,
            "remote",
        ),
    )
    connection.execute(
        "insert into team_members (team_id, employee_id, role_in_team) values (%s, %s, %s)",
        (team_id, employee_id, "developer"),
    )
    return team_id, employee_id


def _insert_employee_into_team(
    connection: psycopg.Connection[tuple[object, ...]],
    team_id: UUID,
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
            "employee",
            f"Employee {uuid4().hex[:6]}",
            f"availability-{uuid4().hex}@example.com",
            "UTC",
            "remote",
        ),
    )
    connection.execute(
        "insert into team_members (team_id, employee_id, role_in_team) values (%s, %s, %s)",
        (team_id, employee_id, "developer"),
    )
    return employee_id


def _insert_schedule(
    connection: psycopg.Connection[tuple[object, ...]],
    employee_id: UUID,
    start_time: time,
    end_time: time,
) -> None:
    connection.execute(
        """
        insert into work_schedules (
            id,
            employee_id,
            work_days,
            start_time,
            end_time,
            timezone,
            last_updated_at,
            is_active
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            uuid4(),
            employee_id,
            [0, 1, 2, 3, 4],
            start_time,
            end_time,
            "UTC",
            datetime(2026, 5, 24, tzinfo=UTC),
            True,
        ),
    )


@pytest.mark.asyncio
async def test_team_availability_and_meeting_recommendations_overlap(
    client: AsyncClient,
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        team_id, employee_one_id = _insert_team_with_employee(connection)
        employee_two_id = _insert_employee_into_team(connection, team_id)
        _insert_schedule(connection, employee_one_id, time(9, 0), time(17, 0))
        _insert_schedule(connection, employee_two_id, time(10, 0), time(16, 0))
        connection.execute(
            """
            insert into activity_events (
                id, employee_id, source, event_type, title, start_dt, end_dt, timezone,
                is_recurring, is_outside_schedule
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                uuid4(),
                employee_one_id,
                "manual",
                "busy",
                "Busy",
                datetime(2026, 5, 25, 10, 0, tzinfo=UTC),
                datetime(2026, 5, 25, 11, 0, tzinfo=UTC),
                "UTC",
                False,
                False,
            ),
        )

    start_dt = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    end_dt = start_dt + timedelta(hours=8)
    availability_response = await client.get(
        f"/api/v1/teams/{team_id}/availability",
        params={"start_dt": start_dt.isoformat(), "end_dt": end_dt.isoformat()},
    )
    meeting_response = await client.post(
        f"/api/v1/teams/{team_id}/meeting-recommendations",
        json={
            "start_dt": start_dt.isoformat(),
            "end_dt": end_dt.isoformat(),
            "duration_minutes": 60,
        },
    )

    assert availability_response.status_code == 200
    assert len(availability_response.json()["employees"]) == 2
    assert meeting_response.status_code == 200
    first_window = meeting_response.json()[0]
    assert first_window["score"] == 1.0
    assert set(first_window["available_employee_ids"]) == {
        str(employee_one_id),
        str(employee_two_id),
    }


@pytest.mark.asyncio
async def test_meeting_recommendations_non_overlapping_schedules(client: AsyncClient) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        team_id, employee_one_id = _insert_team_with_employee(connection)
        employee_two_id = _insert_employee_into_team(connection, team_id)
        _insert_schedule(connection, employee_one_id, time(9, 0), time(10, 0))
        _insert_schedule(connection, employee_two_id, time(11, 0), time(12, 0))

    start_dt = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    end_dt = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    response = await client.post(
        f"/api/v1/teams/{team_id}/meeting-recommendations",
        json={
            "start_dt": start_dt.isoformat(),
            "end_dt": end_dt.isoformat(),
            "duration_minutes": 60,
        },
    )

    assert response.status_code == 200
    assert response.json()
    assert response.json()[0]["score"] == 0.5
    assert len(response.json()[0]["available_employee_ids"]) == 1
