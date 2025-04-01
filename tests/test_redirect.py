import pytest_asyncio
import httpx
from app import app


@pytest_asyncio.fixture
async def async_client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


import pytest


@pytest.mark.asyncio
async def test_redirect(async_client, monkeypatch):
    # Переопределяем update_link_stats, чтобы не вызывать обращение к базе
    monkeypatch.setattr("api.links.update_link_stats", lambda short_code: None)
    # Для публичного редиректа мокаем redis_client.get, чтобы для ключа "url:abc123" вернуть нужный URL
    from api.links import redis_client
    monkeypatch.setattr(redis_client, "get",
                        lambda key: "https://example.com" if key == "url:abc123" else None)

    response = await async_client.get("/api/links/public/abc123", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com"