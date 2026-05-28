"""RBAC + контрактные тесты для schedule confirmation endpoints.

Не нужны БД и сидерные данные: 403 возвращается до запроса в БД,
а path-уровневые проверки авторизации валидируются через override get_current_employee.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


# ---------- POST /employees/{id}/schedule/confirmation-requests ----------


@pytest.mark.asyncio
@pytest.mark.auth_role("employee")
async def test_create_confirmation_request_forbidden_for_employee(
    client: AsyncClient,
) -> None:
    response = await client.post(
        f"/api/v1/employees/{uuid4()}/schedule/confirmation-requests",
        json={"reason": "test"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("analyst")
async def test_create_confirmation_request_forbidden_for_analyst(
    client: AsyncClient,
) -> None:
    response = await client.post(
        f"/api/v1/employees/{uuid4()}/schedule/confirmation-requests",
        json={"reason": "test"},
    )
    assert response.status_code == 403


# ---------- POST /employees/{id}/schedule/confirm ----------


@pytest.mark.asyncio
@pytest.mark.auth_role("employee")
async def test_confirm_schedule_forbidden_for_other_employee(client: AsyncClient) -> None:
    response = await client.post(f"/api/v1/employees/{uuid4()}/schedule/confirm")
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("analyst")
async def test_confirm_schedule_forbidden_for_analyst(client: AsyncClient) -> None:
    response = await client.post(f"/api/v1/employees/{uuid4()}/schedule/confirm")
    assert response.status_code == 403


# ---------- POST /employees/{id}/schedule/confirmation-requests/{rid}/decline ----------


@pytest.mark.asyncio
@pytest.mark.auth_role("hr")
async def test_decline_confirmation_request_forbidden_for_non_target(
    client: AsyncClient,
) -> None:
    response = await client.post(
        f"/api/v1/employees/{uuid4()}/schedule/confirmation-requests/{uuid4()}/decline",
        json={"note": "no"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.auth_role("manager")
async def test_decline_confirmation_request_forbidden_for_manager(
    client: AsyncClient,
) -> None:
    response = await client.post(
        f"/api/v1/employees/{uuid4()}/schedule/confirmation-requests/{uuid4()}/decline",
        json={"note": "no"},
    )
    assert response.status_code == 403
