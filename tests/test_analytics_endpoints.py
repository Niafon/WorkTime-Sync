from datetime import UTC, datetime, timedelta
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
        pytest.skip(f"PostgreSQL is not available for analytics endpoint tests: {exc}")


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


def _insert_employee(connection: psycopg.Connection, employee_id: UUID, label: str) -> None:
    connection.execute(
        """
        insert into employees (id, role, full_name, email, timezone, work_format)
        values (%s, %s, %s, %s, %s, %s)
        """,
        (
            employee_id,
            "employee",
            f"Employee {label}",
            f"analytics-{label}-{uuid4().hex}@example.com",
            "Europe/Moscow",
            "remote",
        ),
    )


def _insert_snapshot(
    connection: psycopg.Connection,
    *,
    employee_id: UUID,
    taken_at: datetime,
    actuality: float,
    conflict_rate: float = 0.1,
    load_level: float = 0.5,
    risk_score: float = 0.4,
    risk_level: str = "medium",
    days_since_update: int = 10,
) -> None:
    connection.execute(
        """
        insert into employee_metric_snapshots (
            id, employee_id, taken_at, days_since_update, actuality_score,
            outside_events_count, total_events_count, conflict_rate,
            load_level, zone_factor, hr_factor, risk_score, risk_level
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            uuid4(),
            employee_id,
            taken_at,
            days_since_update,
            actuality,
            0,
            5,
            conflict_rate,
            load_level,
            0.0,
            0.0,
            risk_score,
            risk_level,
        ),
    )


@pytest.mark.asyncio
async def test_actuality_history_groups_by_month(client: AsyncClient) -> None:
    employee_id = uuid4()
    with psycopg.connect(_sync_database_url()) as connection:
        _insert_employee(connection, employee_id, "ai")
        _insert_snapshot(
            connection,
            employee_id=employee_id,
            taken_at=datetime(2026, 3, 5, 12, 0, tzinfo=UTC),
            actuality=0.4,
        )
        _insert_snapshot(
            connection,
            employee_id=employee_id,
            taken_at=datetime(2026, 3, 20, 12, 0, tzinfo=UTC),
            actuality=0.6,
        )
        _insert_snapshot(
            connection,
            employee_id=employee_id,
            taken_at=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
            actuality=0.8,
        )

    response = await client.get("/api/v1/analytics/actuality-history?months=12")

    assert response.status_code == 200
    points = response.json()
    by_month = {point["month"]: point["value"] for point in points}
    assert by_month["2026-03"] == pytest.approx(0.5, abs=0.001)
    assert by_month["2026-04"] == pytest.approx(0.8, abs=0.001)


@pytest.mark.asyncio
async def test_risk_distribution_history_counts_per_level(client: AsyncClient) -> None:
    employees = [uuid4(), uuid4(), uuid4()]
    taken_at = datetime(2026, 4, 15, 12, 0, tzinfo=UTC)
    with psycopg.connect(_sync_database_url()) as connection:
        for idx, employee_id in enumerate(employees):
            _insert_employee(connection, employee_id, f"risk-{idx}")
        _insert_snapshot(
            connection, employee_id=employees[0], taken_at=taken_at,
            actuality=0.9, risk_level="low", risk_score=0.1,
        )
        _insert_snapshot(
            connection, employee_id=employees[1], taken_at=taken_at,
            actuality=0.5, risk_level="medium", risk_score=0.45,
        )
        _insert_snapshot(
            connection, employee_id=employees[2], taken_at=taken_at,
            actuality=0.2, risk_level="critical", risk_score=0.9,
        )

    response = await client.get("/api/v1/analytics/risk-distribution-history?months=3")

    assert response.status_code == 200
    points = response.json()
    by_month = {point["month"]: point for point in points}
    assert by_month["2026-04"]["low"] == 1
    assert by_month["2026-04"]["medium"] == 1
    assert by_month["2026-04"]["critical"] == 1
    assert by_month["2026-04"]["high"] == 0


@pytest.mark.asyncio
async def test_team_rating_sorts_low_actuality_first(client: AsyncClient) -> None:
    team_low_id = uuid4()
    team_high_id = uuid4()
    employee_low = uuid4()
    employee_high = uuid4()
    with psycopg.connect(_sync_database_url()) as connection:
        _insert_employee(connection, employee_low, "low-team-member")
        _insert_employee(connection, employee_high, "high-team-member")
        connection.execute(
            "insert into teams (id, name) values (%s, %s), (%s, %s)",
            (team_low_id, "Aaa Low Team", team_high_id, "Zzz High Team"),
        )
        connection.execute(
            "insert into team_members (team_id, employee_id, role_in_team) "
            "values (%s, %s, %s), (%s, %s, %s)",
            (team_low_id, employee_low, "dev", team_high_id, employee_high, "dev"),
        )
        for employee_id, actuality, risk_score, risk_level in (
            (employee_low, 0.2, 0.85, "critical"),
            (employee_high, 0.95, 0.1, "low"),
        ):
            connection.execute(
                """
                insert into employee_metrics (
                    id, employee_id, calculated_at, days_since_update, actuality_score,
                    outside_events_count, total_events_count, conflict_rate,
                    load_level, zone_factor, hr_factor, risk_score, risk_level
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    uuid4(),
                    employee_id,
                    datetime(2026, 5, 24, tzinfo=UTC),
                    0,
                    actuality,
                    0,
                    10,
                    0.1,
                    0.5,
                    0.0,
                    0.0,
                    risk_score,
                    risk_level,
                ),
            )

    response = await client.get("/api/v1/analytics/team-rating?limit=10")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    assert items[0]["team_id"] == str(team_low_id)
    assert items[0]["avg_actuality"] == pytest.approx(0.2)
    assert items[0]["attention_count"] == 1
    assert items[1]["team_id"] == str(team_high_id)


@pytest.mark.asyncio
async def test_summary_deltas_compares_two_windows(client: AsyncClient) -> None:
    employee_id = uuid4()
    now = datetime.now(UTC)
    with psycopg.connect(_sync_database_url()) as connection:
        _insert_employee(connection, employee_id, "deltas")
        _insert_snapshot(
            connection,
            employee_id=employee_id,
            taken_at=now - timedelta(days=2),
            actuality=0.9,
            conflict_rate=0.05,
        )
        _insert_snapshot(
            connection,
            employee_id=employee_id,
            taken_at=now - timedelta(days=10),
            actuality=0.5,
            conflict_rate=0.25,
        )

    response = await client.get("/api/v1/analytics/summary-deltas?period=week")

    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "week"
    assert body["ai_delta"] == pytest.approx(0.4, abs=0.001)
    assert body["ci_delta"] == pytest.approx(-0.2, abs=0.001)


@pytest.mark.asyncio
async def test_actuality_history_empty_returns_empty_list(client: AsyncClient) -> None:
    response = await client.get("/api/v1/analytics/actuality-history")

    assert response.status_code == 200
    assert response.json() == []


def _insert_team(connection: psycopg.Connection, team_id: UUID, name: str) -> None:
    connection.execute(
        "insert into teams (id, name) values (%s, %s)",
        (team_id, name),
    )


def _add_to_team(
    connection: psycopg.Connection,
    team_id: UUID,
    employee_id: UUID,
    role_in_team: str = "member",
) -> None:
    connection.execute(
        "insert into team_members (team_id, employee_id, role_in_team) values (%s, %s, %s)",
        (team_id, employee_id, role_in_team),
    )


@pytest.mark.asyncio
async def test_team_metrics_history_empty_when_no_snapshots(client: AsyncClient) -> None:
    team_id = uuid4()
    with psycopg.connect(_sync_database_url()) as connection:
        _insert_team(connection, team_id, "Empty Team")

    response = await client.get(f"/api/v1/analytics/teams/{team_id}/metrics-history")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_team_metrics_history_groups_by_month_with_attention(
    client: AsyncClient,
) -> None:
    team_id = uuid4()
    employee_a = uuid4()
    employee_b = uuid4()
    with psycopg.connect(_sync_database_url()) as connection:
        _insert_team(connection, team_id, "Squad")
        _insert_employee(connection, employee_a, "team-a")
        _insert_employee(connection, employee_b, "team-b")
        _add_to_team(connection, team_id, employee_a)
        _add_to_team(connection, team_id, employee_b)
        # Март: один critical (attention), один medium → attention_count=1
        _insert_snapshot(
            connection,
            employee_id=employee_a,
            taken_at=datetime(2026, 3, 10, 12, 0, tzinfo=UTC),
            actuality=0.4,
            risk_score=0.9,
            risk_level="critical",
        )
        _insert_snapshot(
            connection,
            employee_id=employee_b,
            taken_at=datetime(2026, 3, 20, 12, 0, tzinfo=UTC),
            actuality=0.6,
            risk_score=0.3,
            risk_level="medium",
        )
        # Апрель: оба high → attention_count=2
        _insert_snapshot(
            connection,
            employee_id=employee_a,
            taken_at=datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
            actuality=0.7,
            risk_score=0.7,
            risk_level="high",
        )
        _insert_snapshot(
            connection,
            employee_id=employee_b,
            taken_at=datetime(2026, 4, 15, 12, 0, tzinfo=UTC),
            actuality=0.5,
            risk_score=0.8,
            risk_level="high",
        )

    response = await client.get(
        f"/api/v1/analytics/teams/{team_id}/metrics-history?months=12"
    )

    assert response.status_code == 200
    by_month = {point["month"]: point for point in response.json()}

    march = by_month["2026-03"]
    assert march["avg_actuality"] == pytest.approx(0.5, abs=0.001)
    assert march["avg_risk_score"] == pytest.approx(0.6, abs=0.001)
    assert march["attention_count"] == 1

    april = by_month["2026-04"]
    assert april["avg_actuality"] == pytest.approx(0.6, abs=0.001)
    assert april["avg_risk_score"] == pytest.approx(0.75, abs=0.001)
    assert april["attention_count"] == 2


@pytest.mark.asyncio
async def test_team_metrics_history_excludes_other_teams(client: AsyncClient) -> None:
    target_team = uuid4()
    other_team = uuid4()
    target_emp = uuid4()
    other_emp = uuid4()
    taken_at = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    with psycopg.connect(_sync_database_url()) as connection:
        _insert_team(connection, target_team, "Target")
        _insert_team(connection, other_team, "Other")
        _insert_employee(connection, target_emp, "target")
        _insert_employee(connection, other_emp, "other")
        _add_to_team(connection, target_team, target_emp)
        _add_to_team(connection, other_team, other_emp)
        # Снимок целевой команды: Ai=0.3
        _insert_snapshot(
            connection,
            employee_id=target_emp,
            taken_at=taken_at,
            actuality=0.3,
            risk_score=0.5,
            risk_level="medium",
        )
        # Снимок другой команды: не должен попасть в агрегат
        _insert_snapshot(
            connection,
            employee_id=other_emp,
            taken_at=taken_at,
            actuality=0.9,
            risk_score=0.1,
            risk_level="low",
        )

    response = await client.get(
        f"/api/v1/analytics/teams/{target_team}/metrics-history?months=12"
    )

    assert response.status_code == 200
    points = response.json()
    assert len(points) == 1
    assert points[0]["month"] == "2026-04"
    assert points[0]["avg_actuality"] == pytest.approx(0.3, abs=0.001)
    assert points[0]["attention_count"] == 0
