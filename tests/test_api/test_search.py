import pytest


class TestSearchByPartNumber:
    async def test_search_by_part_number_returns_200(self, app_client, sample_part):
        response = await app_client.get("/api/v1/search?q=04C100032F")
        assert response.status_code == 200

    async def test_search_returns_breadcrumb(self, app_client, sample_part):
        response = await app_client.get("/api/v1/search?q=04C100032F")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0
        item = data["items"][0]
        assert "breadcrumb" in item
        breadcrumb = item["breadcrumb"]
        # breadcrumb should contain brand, model, year, category, subgroup context
        assert isinstance(breadcrumb, dict)
        assert "brand" in breadcrumb or "model" in breadcrumb

    async def test_search_pagination(self, app_client, sample_part):
        response = await app_client.get("/api/v1/search?q=04C100032F&page=1&per_page=10")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "pages" in data
        assert data["page"] == 1
        assert data["per_page"] == 10

    async def test_search_empty_returns_empty_items(self, app_client):
        response = await app_client.get("/api/v1/search?q=ZZZNONONEXISTENTPART999")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["items"] == []
        assert data["total"] == 0
