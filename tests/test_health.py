import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_returns_ok_or_degraded() -> None:
    """Health-check теперь подтверждает доступность БД.

    Под pytest без поднятого Postgres вернётся 503 + degraded, под нормальным
    окружением — 200 + ok. Оба варианта валидны: важно, что endpoint живой,
    а статус честно отражает реальное состояние БД.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code in {200, 503}
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["database"] in {"up", "down"}
