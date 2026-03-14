import pytest

from app.services.parts_service import PartsService


class TestSearchByPartNumber:
    async def test_search_by_part_number(self, db_session, sample_part):
        service = PartsService(db_session)
        result = await service.search_by_part_number("04C100032F")
        assert result is not None
        assert "items" in result
        assert len(result["items"]) >= 1
        part_numbers = [p["part_number"] for p in result["items"]]
        assert "04C100032F" in part_numbers

    async def test_search_by_part_number_partial_match(self, db_session, sample_part):
        service = PartsService(db_session)
        result = await service.search_by_part_number("04C100")
        assert result is not None
        assert "items" in result
        assert len(result["items"]) >= 1

    async def test_search_by_part_number_no_match(self, db_session, sample_part):
        service = PartsService(db_session)
        result = await service.search_by_part_number("ZZZNONONEXISTENT999")
        assert result is not None
        assert "items" in result
        assert len(result["items"]) == 0
        assert result["total"] == 0

    async def test_search_by_part_number_returns_pagination(self, db_session, sample_part):
        service = PartsService(db_session)
        result = await service.search_by_part_number("04C100032F", page=1, per_page=10)
        assert "total" in result
        assert "page" in result
        assert "per_page" in result
        assert "pages" in result


class TestSearchByDescription:
    async def test_search_by_description(self, db_session, sample_part):
        service = PartsService(db_session)
        result = await service.search_by_description("Short engine")
        assert result is not None
        assert "items" in result
        assert len(result["items"]) >= 1
        descriptions = [p["description"] for p in result["items"]]
        assert any("Short engine" in d for d in descriptions)

    async def test_search_by_description_partial(self, db_session, sample_part):
        service = PartsService(db_session)
        result = await service.search_by_description("Short")
        assert result is not None
        assert "items" in result
        assert len(result["items"]) >= 1

    async def test_search_by_description_no_match(self, db_session):
        service = PartsService(db_session)
        result = await service.search_by_description("ZZZNonExistentDescription999")
        assert result is not None
        assert "items" in result
        assert len(result["items"]) == 0


class TestSearchReturnsBreadcrumb:
    async def test_search_returns_breadcrumb(
        self,
        db_session,
        sample_part,
        sample_subgroup,
        sample_category,
        sample_model_year,
        sample_model,
        sample_brand,
    ):
        service = PartsService(db_session)
        result = await service.search_by_part_number("04C100032F")
        assert result is not None
        assert "items" in result
        assert len(result["items"]) >= 1
        item = result["items"][0]
        assert "breadcrumb" in item
        breadcrumb = item["breadcrumb"]
        assert isinstance(breadcrumb, dict)
        # breadcrumb must contain navigation context
        assert "brand" in breadcrumb or "model" in breadcrumb or "category" in breadcrumb

    async def test_search_breadcrumb_has_brand_info(
        self,
        db_session,
        sample_part,
        sample_subgroup,
        sample_category,
        sample_model_year,
        sample_model,
        sample_brand,
    ):
        service = PartsService(db_session)
        result = await service.search_by_part_number("04C100032F")
        item = result["items"][0]
        breadcrumb = item["breadcrumb"]
        assert "brand" in breadcrumb
        assert breadcrumb["brand"]["name"] == "Volkswagen"

    async def test_search_breadcrumb_has_model_info(
        self,
        db_session,
        sample_part,
        sample_subgroup,
        sample_category,
        sample_model_year,
        sample_model,
        sample_brand,
    ):
        service = PartsService(db_session)
        result = await service.search_by_part_number("04C100032F")
        item = result["items"][0]
        breadcrumb = item["breadcrumb"]
        assert "model" in breadcrumb
        assert breadcrumb["model"]["name"] == "Golf/Variant/4Motion"


class TestSearchPagination:
    async def test_search_pagination_first_page(self, db_session, sample_part):
        service = PartsService(db_session)
        result = await service.search_by_part_number("04C100032F", page=1, per_page=5)
        assert result["page"] == 1
        assert result["per_page"] == 5

    async def test_search_pagination_calculates_pages(self, db_session, sample_part):
        service = PartsService(db_session)
        result = await service.search_by_part_number("04C100032F", page=1, per_page=1)
        assert result["pages"] >= 1
        assert result["total"] >= 1

    async def test_search_pagination_empty_result(self, db_session):
        service = PartsService(db_session)
        result = await service.search_by_part_number("ZZZNONONEXISTENT999", page=1, per_page=10)
        assert result["total"] == 0
        assert result["pages"] == 0
        assert result["items"] == []
