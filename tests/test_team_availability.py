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
    *,
    employee_timezone: str = "UTC",
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
            employee_timezone,
            "remote",
        ),
    )
    connection.execute(
        "insert into team_members (team_id, employee_id, role_in_team) values (%s, %s, %s)",
        (team_id, employee_id, "developer"),
    )
    return employee_id


def _insert_load_metric(
    connection: psycopg.Connection[tuple[object, ...]],
    employee_id: UUID,
    load_level: float,
) -> None:
    connection.execute(
        """
        insert into employee_metrics (
            id, employee_id, calculated_at, days_since_update, actuality_score,
            outside_events_count, total_events_count, conflict_rate,
            load_level, risk_score, risk_level
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            uuid4(),
            employee_id,
            datetime(2026, 5, 24, tzinfo=UTC),
            0,
            1.0,
            0,
            0,
            0.0,
            load_level,
            0.0,
            "low",
        ),
    )


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
    assert first_window["score"] == pytest.approx(0.6)
    assert set(first_window["required_available_ids"]) == {
        str(employee_one_id),
        str(employee_two_id),
    }
    assert first_window["required_missing_ids"] == []
    assert first_window["overloaded_employee_ids"] == []
    assert set(first_window["available_employee_ids"]) == {
        str(employee_one_id),
        str(employee_two_id),
    }


@pytest.mark.asyncio
async def test_meeting_recommendations_skip_slots_without_all_required(
    client: AsyncClient,
) -> None:
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
    assert response.json() == []


@pytest.mark.asyncio
async def test_meeting_recommendation_excludes_overloaded_employee(
    client: AsyncClient,
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        team_id, employee_one_id = _insert_team_with_employee(connection)
        employee_two_id = _insert_employee_into_team(connection, team_id)
        _insert_schedule(connection, employee_one_id, time(9, 0), time(17, 0))
        _insert_schedule(connection, employee_two_id, time(9, 0), time(17, 0))
        _insert_load_metric(connection, employee_one_id, 0.9)
        _insert_load_metric(connection, employee_two_id, 0.5)

    start_dt = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    end_dt = start_dt + timedelta(hours=4)
    response = await client.post(
        f"/api/v1/teams/{team_id}/meeting-recommendations",
        json={
            "start_dt": start_dt.isoformat(),
            "end_dt": end_dt.isoformat(),
            "duration_minutes": 60,
            "required_employee_ids": [str(employee_two_id)],
            "optional_employee_ids": [str(employee_one_id)],
            "load_threshold": 0.8,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body
    first = body[0]
    assert first["required_available_ids"] == [str(employee_two_id)]
    assert first["overloaded_employee_ids"] == [str(employee_one_id)]
    assert str(employee_one_id) not in first["optional_available_ids"]
    assert str(employee_one_id) in first["unavailable_employee_ids"]


@pytest.mark.asyncio
async def test_meeting_recommendation_requires_required_participants(
    client: AsyncClient,
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        team_id, employee_a = _insert_team_with_employee(connection)
        employee_b = _insert_employee_into_team(connection, team_id)
        employee_c = _insert_employee_into_team(connection, team_id)
        _insert_schedule(connection, employee_a, time(9, 0), time(10, 0))
        _insert_schedule(connection, employee_b, time(9, 0), time(17, 0))
        _insert_schedule(connection, employee_c, time(9, 0), time(17, 0))

    start_dt = datetime(2026, 5, 25, 11, 0, tzinfo=UTC)
    end_dt = datetime(2026, 5, 25, 17, 0, tzinfo=UTC)
    response = await client.post(
        f"/api/v1/teams/{team_id}/meeting-recommendations",
        json={
            "start_dt": start_dt.isoformat(),
            "end_dt": end_dt.isoformat(),
            "duration_minutes": 60,
            "required_employee_ids": [str(employee_a)],
            "optional_employee_ids": [str(employee_b), str(employee_c)],
        },
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_meeting_recommendation_returns_per_employee_local_times(
    client: AsyncClient,
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        team_id, employee_msk = _insert_team_with_employee(
            connection, employee_timezone="Europe/Moscow"
        )
        employee_ekb = _insert_employee_into_team(
            connection, team_id, employee_timezone="Asia/Yekaterinburg"
        )
        _insert_schedule(connection, employee_msk, time(9, 0), time(17, 0))
        _insert_schedule(connection, employee_ekb, time(9, 0), time(17, 0))

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
    first = response.json()[0]
    local_by_employee = {item["employee_id"]: item for item in first["local_times"]}
    assert local_by_employee[str(employee_msk)]["local_start"].endswith("+03:00")
    assert local_by_employee[str(employee_ekb)]["local_start"].endswith("+05:00")


@pytest.mark.asyncio
async def test_recurring_busy_event_blocks_every_occurrence(
    client: AsyncClient,
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        team_id, employee_id = _insert_team_with_employee(connection)
        _insert_schedule(connection, employee_id, time(9, 0), time(17, 0))
        # 2026-05-25 — Monday. WEEKLY;BYDAY=MO для 4 недель → 4 occurrences.
        connection.execute(
            """
            insert into activity_events (
                id, employee_id, source, event_type, title, start_dt, end_dt, timezone,
                recurrence_rule, is_recurring, is_outside_schedule
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                uuid4(),
                employee_id,
                "manual",
                "busy",
                "Weekly standup",
                datetime(2026, 5, 25, 10, 0, tzinfo=UTC),
                datetime(2026, 5, 25, 11, 0, tzinfo=UTC),
                "UTC",
                "FREQ=WEEKLY;BYDAY=MO;COUNT=4",
                True,
                False,
            ),
        )

    # 4 понедельника подряд: 25 мая, 1, 8, 15 июня.
    for monday in (
        datetime(2026, 5, 25, tzinfo=UTC),
        datetime(2026, 6, 1, tzinfo=UTC),
        datetime(2026, 6, 8, tzinfo=UTC),
        datetime(2026, 6, 15, tzinfo=UTC),
    ):
        start_dt = monday.replace(hour=10, minute=0)
        end_dt = monday.replace(hour=11, minute=0)
        response = await client.post(
            f"/api/v1/teams/{team_id}/meeting-recommendations",
            json={
                "start_dt": start_dt.isoformat(),
                "end_dt": end_dt.isoformat(),
                "duration_minutes": 60,
                "required_employee_ids": [str(employee_id)],
            },
        )

        assert response.status_code == 200, monday.isoformat()
        assert response.json() == [], (
            f"recurring busy event must block {monday.date()} 10:00–11:00, "
            f"but got {response.json()}"
        )


@pytest.mark.asyncio
async def test_meeting_recommendation_optional_participants_boost_score(
    client: AsyncClient,
) -> None:
    with psycopg.connect(_sync_database_url()) as connection:
        team_id, employee_a = _insert_team_with_employee(connection)
        employee_b = _insert_employee_into_team(connection, team_id)
        _insert_schedule(connection, employee_a, time(9, 0), time(17, 0))
        _insert_schedule(connection, employee_b, time(10, 0), time(11, 0))

    start_dt = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    end_dt = datetime(2026, 5, 25, 13, 0, tzinfo=UTC)
    response = await client.post(
        f"/api/v1/teams/{team_id}/meeting-recommendations",
        json={
            "start_dt": start_dt.isoformat(),
            "end_dt": end_dt.isoformat(),
            "duration_minutes": 60,
            "required_employee_ids": [str(employee_a)],
            "optional_employee_ids": [str(employee_b)],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body
    windows_with_b = [w for w in body if str(employee_b) in w["optional_available_ids"]]
    windows_without_b = [w for w in body if str(employee_b) not in w["optional_available_ids"]]
    assert windows_with_b
    if windows_without_b:
        assert windows_with_b[0]["score"] > windows_without_b[0]["score"]
