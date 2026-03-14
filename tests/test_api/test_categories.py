import pytest


class TestGetYearCategories:
    async def test_get_year_categories_returns_200(
        self, app_client, sample_model_year, sample_category
    ):
        response = await app_client.get(
            f"/api/v1/model-years/{sample_model_year.id}/categories"
        )
        assert response.status_code == 200

    async def test_get_year_categories_returns_list(
        self, app_client, sample_model_year, sample_category
    ):
        response = await app_client.get(
            f"/api/v1/model-years/{sample_model_year.id}/categories"
        )
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0

    async def test_get_year_categories_not_found_returns_404(self, app_client):
        response = await app_client.get("/api/v1/model-years/999999/categories")
        assert response.status_code == 404


class TestGetCategorySubgroups:
    async def test_get_category_subgroups_returns_200(
        self, app_client, sample_category, sample_subgroup
    ):
        response = await app_client.get(
            f"/api/v1/categories/{sample_category.id}/subgroups"
        )
        assert response.status_code == 200

    async def test_get_category_subgroups_returns_list(
        self, app_client, sample_category, sample_subgroup
    ):
        response = await app_client.get(
            f"/api/v1/categories/{sample_category.id}/subgroups"
        )
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0

    async def test_get_category_subgroups_not_found_returns_404(self, app_client):
        response = await app_client.get("/api/v1/categories/999999/subgroups")
        assert response.status_code == 404


class TestGetSubgroupParts:
    async def test_get_subgroup_parts_returns_200(
        self, app_client, sample_subgroup, sample_part
    ):
        response = await app_client.get(
            f"/api/v1/subgroups/{sample_subgroup.id}/parts"
        )
        assert response.status_code == 200

    async def test_get_subgroup_parts_returns_list(
        self, app_client, sample_subgroup, sample_part
    ):
        response = await app_client.get(
            f"/api/v1/subgroups/{sample_subgroup.id}/parts"
        )
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0

    async def test_get_subgroup_parts_not_found_returns_404(self, app_client):
        response = await app_client.get("/api/v1/subgroups/999999/parts")
        assert response.status_code == 404
