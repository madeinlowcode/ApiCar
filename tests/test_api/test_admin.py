import pytest


VALID_API_KEY = "change-me-in-production"


class TestAdminAuthentication:
    async def test_admin_without_api_key_returns_401(self, app_client):
        response = await app_client.get("/api/v1/admin/crawl/status")
        assert response.status_code == 401

    async def test_admin_with_invalid_key_returns_401(self, app_client):
        response = await app_client.get(
            "/api/v1/admin/crawl/status",
            headers={"X-API-Key": "wrong-key-totally-invalid"},
        )
        assert response.status_code == 401

    async def test_admin_with_valid_key_returns_200(self, app_client):
        response = await app_client.get(
            "/api/v1/admin/crawl/status",
            headers={"X-API-Key": VALID_API_KEY},
        )
        assert response.status_code == 200


class TestAdminCrawlStatus:
    async def test_crawl_status_returns_200(self, app_client):
        response = await app_client.get(
            "/api/v1/admin/crawl/status",
            headers={"X-API-Key": VALID_API_KEY},
        )
        assert response.status_code == 200

    async def test_crawl_status_has_expected_fields(self, app_client):
        response = await app_client.get(
            "/api/v1/admin/crawl/status",
            headers={"X-API-Key": VALID_API_KEY},
        )
        data = response.json()
        assert "jobs" in data

    async def test_crawl_failed_returns_200(self, app_client):
        response = await app_client.get(
            "/api/v1/admin/crawl/failed",
            headers={"X-API-Key": VALID_API_KEY},
        )
        assert response.status_code == 200

    async def test_crawl_failed_returns_list(self, app_client):
        response = await app_client.get(
            "/api/v1/admin/crawl/failed",
            headers={"X-API-Key": VALID_API_KEY},
        )
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
