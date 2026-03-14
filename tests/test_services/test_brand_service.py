import pytest

from app.services.brand_service import BrandService


class TestListBrands:
    async def test_list_brands_returns_all(self, db_session, sample_brand):
        service = BrandService(db_session)
        result = await service.list_brands()
        assert result is not None
        assert "items" in result
        assert len(result["items"]) >= 1
        brand_names = [b["name"] for b in result["items"]]
        assert "Volkswagen" in brand_names

    async def test_list_brands_filter_by_region(self, db_session, sample_brand):
        service = BrandService(db_session)
        result = await service.list_brands(region="Europe")
        assert result is not None
        assert "items" in result
        for brand in result["items"]:
            assert brand["region"] == "Europe"

    async def test_list_brands_filter_by_region_excludes_others(self, db_session, sample_brand):
        service = BrandService(db_session)
        result = await service.list_brands(region="Japan")
        assert result is not None
        assert "items" in result
        assert all(b["region"] == "Japan" for b in result["items"])

    async def test_list_brands_search(self, db_session, sample_brand):
        service = BrandService(db_session)
        result = await service.list_brands(search="Volks")
        assert result is not None
        assert "items" in result
        assert len(result["items"]) >= 1
        assert any("Volkswagen" in b["name"] for b in result["items"])

    async def test_list_brands_search_no_match(self, db_session, sample_brand):
        service = BrandService(db_session)
        result = await service.list_brands(search="ZZZNonExistentBrand999")
        assert result is not None
        assert "items" in result
        assert len(result["items"]) == 0

    async def test_list_brands_returns_pagination_metadata(self, db_session, sample_brand):
        service = BrandService(db_session)
        result = await service.list_brands(page=1, per_page=10)
        assert "total" in result
        assert "page" in result
        assert "per_page" in result
        assert "pages" in result
        assert result["page"] == 1
        assert result["per_page"] == 10


class TestGetBrandBySlug:
    async def test_get_brand_by_slug(self, db_session, sample_brand):
        service = BrandService(db_session)
        result = await service.get_brand_by_slug("volkswagen")
        assert result is not None
        assert result["slug"] == "volkswagen"
        assert result["name"] == "Volkswagen"

    async def test_get_brand_by_slug_includes_markets(
        self, db_session, sample_brand, sample_market
    ):
        service = BrandService(db_session)
        result = await service.get_brand_by_slug("volkswagen")
        assert result is not None
        assert "markets" in result
        assert isinstance(result["markets"], list)
        assert len(result["markets"]) >= 1

    async def test_get_brand_by_slug_not_found(self, db_session):
        service = BrandService(db_session)
        result = await service.get_brand_by_slug("nonexistent-brand-xyz")
        assert result is None
