import pytest


class TestGetModel:
    async def test_get_model_returns_200(self, app_client, sample_model):
        response = await app_client.get(f"/api/v1/models/{sample_model.id}")
        assert response.status_code == 200

    async def test_get_model_not_found_404(self, app_client):
        response = await app_client.get("/api/v1/models/999999")
        assert response.status_code == 404

    async def test_get_model_not_found_has_error_format(self, app_client):
        response = await app_client.get("/api/v1/models/999999")
        data = response.json()
        assert "error" in data
        error = data["error"]
        assert "code" in error
        assert "message" in error
        assert "status" in error


class TestGetModelYears:
    async def test_get_model_years_returns_200(self, app_client, sample_model, sample_model_year):
        response = await app_client.get(f"/api/v1/models/{sample_model.id}/years")
        assert response.status_code == 200

    async def test_get_model_years_filter_by_year(
        self, app_client, sample_model, sample_model_year
    ):
        response = await app_client.get(f"/api/v1/models/{sample_model.id}/years?year=2015")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        for item in data["items"]:
            assert item["year"] == 2015
