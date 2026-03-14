import pytest


class TestErrorFormat:
    async def test_404_returns_error_object_with_code_message_status(self, app_client):
        response = await app_client.get("/api/v1/brands/this-brand-does-not-exist")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        error = data["error"]
        assert "code" in error
        assert "message" in error
        assert "status" in error

    async def test_error_code_is_string(self, app_client):
        response = await app_client.get("/api/v1/brands/this-brand-does-not-exist")
        data = response.json()
        error = data["error"]
        assert isinstance(error["code"], str)

    async def test_error_status_is_integer(self, app_client):
        response = await app_client.get("/api/v1/brands/this-brand-does-not-exist")
        data = response.json()
        error = data["error"]
        assert isinstance(error["status"], int)
        assert error["status"] == 404

    async def test_unknown_route_returns_404_error_format(self, app_client):
        response = await app_client.get("/api/v1/completely/unknown/endpoint")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    async def test_error_message_is_string(self, app_client):
        response = await app_client.get("/api/v1/brands/nonexistent")
        data = response.json()
        error = data["error"]
        assert isinstance(error["message"], str)
        assert len(error["message"]) > 0
