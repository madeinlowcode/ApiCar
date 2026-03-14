import pytest


class TestHealthCheck:
    async def test_health_returns_200(self, app_client):
        response = await app_client.get("/health")
        assert response.status_code == 200

    async def test_health_includes_status(self, app_client):
        response = await app_client.get("/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    async def test_health_includes_db_status(self, app_client):
        response = await app_client.get("/health")
        data = response.json()
        assert "database" in data

    async def test_health_includes_redis_status(self, app_client):
        response = await app_client.get("/health")
        data = response.json()
        assert "redis" in data

    async def test_health_includes_version(self, app_client):
        response = await app_client.get("/health")
        data = response.json()
        assert "version" in data
