"""
Tests for BrandModelsParser.

The vw-models-snapshot.yaml represents the VW model list page.
Each row in the table has columns: Catalog (code), Model (name + link), Description,
Production date (e.g. "1998-..."), Production (market codes like "B;D;G;...").

Sample rows extracted from snapshot:
  - code=GO,  name="Golf",               prod_date="1975-1998", markets="B;D;E;K;P;T;W"
  - code=GOLF, name="Golf/Variant/4Motion", prod_date="1998-...", markets="B;D;G;J;K;M;P;R;U;W;Z;9"
  - code=AMA, name="Amarok",              prod_date="2010-...",  markets="A;H;L;1;3;8"
  - code=TIG, name="Tiguan",             prod_date="2008-...",  markets="A;G;J;K;L;W"
  - code=PA,  name="Passat/Variant/Santana", prod_date="1974-...", markets="A;B;C;D;E;G;L;P;S;W;X;Y;Z;9"

The page also lists markets in a side list (Europe, South Africa, USA, etc.).
Total model rows in the snapshot: 57
"""

import pytest
from pathlib import Path

from crawler.parsers.brand_models import BrandModelsParser


SNAPSHOTS_DIR = Path(__file__).parent.parent / "snapshots"


@pytest.fixture
def snapshot_content() -> str:
    with open(SNAPSHOTS_DIR / "vw-models-snapshot.yaml") as f:
        return f.read()


class TestBrandModelsParserReturnType:
    async def test_parse_returns_list(self, snapshot_content):
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        assert isinstance(result, list)

    async def test_parse_returns_non_empty_list(self, snapshot_content):
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        assert len(result) > 0, "BrandModelsParser must not return empty list"

    async def test_each_item_is_dict(self, snapshot_content):
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert isinstance(item, dict)


class TestBrandModelsParserFields:
    async def test_each_model_has_code_field(self, snapshot_content):
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "code" in item, f"Model dict missing 'code': {item}"

    async def test_each_model_has_name_field(self, snapshot_content):
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "name" in item, f"Model dict missing 'name': {item}"

    async def test_each_model_has_url_field(self, snapshot_content):
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "url" in item, f"Model dict missing 'url': {item}"

    async def test_each_model_has_production_date_field(self, snapshot_content):
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "production_date" in item, f"Model dict missing 'production_date': {item}"

    async def test_code_is_non_empty_string(self, snapshot_content):
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert isinstance(item["code"], str) and item["code"].strip() != ""

    async def test_name_is_non_empty_string(self, snapshot_content):
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert isinstance(item["name"], str) and item["name"].strip() != ""


class TestBrandModelsParserCount:
    async def test_parses_57_models(self, snapshot_content):
        """The VW models snapshot contains 57 model rows."""
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        assert len(result) == 57, f"Expected 57 models, got {len(result)}"


class TestBrandModelsParserSpecificModels:
    async def test_golf_model_present(self, snapshot_content):
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        assert "Golf" in names, "Golf model must be in parsed results"

    async def test_golf_variant_model_present(self, snapshot_content):
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        assert "Golf/Variant/4Motion" in names

    async def test_passat_model_present(self, snapshot_content):
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        assert "Passat/Variant/Santana" in names

    async def test_tiguan_model_present(self, snapshot_content):
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        assert "Tiguan" in names

    async def test_golf_code_is_go(self, snapshot_content):
        """Early Golf (1975-1998) has catalog code 'GO'."""
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        golf = next((item for item in result if item.get("name") == "Golf"), None)
        assert golf is not None
        assert golf["code"] == "GO", f"Expected code 'GO', got '{golf['code']}'"

    async def test_golf_production_date(self, snapshot_content):
        """Early Golf production date is 1975-1998."""
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        golf = next((item for item in result if item.get("code") == "GO"), None)
        assert golf is not None
        assert golf["production_date"] == "1975-1998"

    async def test_amarok_production_date_is_open(self, snapshot_content):
        """Amarok production date starts 2010 and is still ongoing (2010-...)."""
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        amarok = next((item for item in result if item.get("code") == "AMA"), None)
        assert amarok is not None
        assert "2010" in amarok["production_date"]
        assert "..." in amarok["production_date"]

    async def test_model_url_contains_catcar(self, snapshot_content):
        """Model URLs should point to catcar.info."""
        parser = BrandModelsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "catcar.info" in item["url"] or item["url"].startswith("http"), (
                f"URL should be absolute and contain catcar.info: {item['url']}"
            )


class TestBrandModelsParserGetValidator:
    def test_get_validator_returns_parsed_model(self):
        from crawler.validators.model import ParsedModel

        parser = BrandModelsParser()
        assert parser.get_validator() is ParsedModel
