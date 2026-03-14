import pytest


class TestGetBrands:
    async def test_get_brands_returns_200(self, app_client, sample_brand):
        response = await app_client.get("/api/v1/brands")
        assert response.status_code == 200

    async def test_get_brands_returns_paginated_response(self, app_client, sample_brand):
        response = await app_client.get("/api/v1/brands")
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "pages" in data

    async def test_get_brands_filter_by_region(self, app_client, sample_brand):
        response = await app_client.get("/api/v1/brands?region=Europe")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        for item in data["items"]:
            assert item["region"] == "Europe"

    async def test_get_brands_search_by_name(self, app_client, sample_brand):
        response = await app_client.get("/api/v1/brands?search=Volkswagen")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert any("Volkswagen" in item["name"] for item in data["items"])


class TestGetBrandBySlug:
    async def test_get_brand_by_slug_returns_200(self, app_client, sample_brand):
        response = await app_client.get("/api/v1/brands/volkswagen")
        assert response.status_code == 200

    async def test_get_brand_by_slug_includes_markets(self, app_client, sample_brand, sample_market):
        response = await app_client.get("/api/v1/brands/volkswagen")
        assert response.status_code == 200
        data = response.json()
        assert "markets" in data
        assert isinstance(data["markets"], list)
        assert len(data["markets"]) > 0

    async def test_get_brand_by_slug_not_found_returns_404(self, app_client):
        response = await app_client.get("/api/v1/brands/nonexistent-brand")
        assert response.status_code == 404

    async def test_get_brand_by_slug_404_has_error_format(self, app_client):
        response = await app_client.get("/api/v1/brands/nonexistent-brand")
        data = response.json()
        assert "error" in data
        error = data["error"]
        assert "code" in error
        assert "message" in error
        assert "status" in error


class TestGetBrandModels:
    async def test_get_brand_models_returns_200(self, app_client, sample_brand, sample_model):
        response = await app_client.get("/api/v1/brands/volkswagen/models")
        assert response.status_code == 200

    async def test_get_brand_models_filter_by_market(
        self, app_client, sample_brand, sample_market, sample_model
    ):
        response = await app_client.get(
            f"/api/v1/brands/volkswagen/models?market_id={sample_market.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        for item in data["items"]:
            assert item["market_id"] == sample_market.id
