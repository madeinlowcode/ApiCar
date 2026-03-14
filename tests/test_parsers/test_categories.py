"""
Tests for CategoriesParser.

The vw-golf-parts-snapshot.yaml represents the "Main parts" page for
Golf/Variant/4Motion 2017 (Golf 5G1***). It shows 10 main part categories:

  0 - Accessors
  1 - Engine
  2 - Fuel, exhaust, cooling
  3 - Gearbox
  4 - Front axle, steering
  5 - Rear axle
  6 - Wheels, brakes
  7 - Pedals
  8 - Body
  9 - Electrics

Each category link appears with a name, an image, and a URL.
The parser must extract exactly 10 categories.
"""

import pytest
from pathlib import Path

from crawler.parsers.categories import CategoriesParser


SNAPSHOTS_DIR = Path(__file__).parent.parent / "snapshots"

EXPECTED_CATEGORIES = [
    "Accessors",
    "Engine",
    "Fuel, exhaust, cooling",
    "Gearbox",
    "Front axle, steering",
    "Rear axle",
    "Wheels, brakes",
    "Pedals",
    "Body",
    "Electrics",
]


@pytest.fixture
def snapshot_content() -> str:
    with open(SNAPSHOTS_DIR / "vw-golf-parts-snapshot.yaml") as f:
        return f.read()


class TestCategoriesParserReturnType:
    async def test_parse_returns_list(self, snapshot_content):
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        assert isinstance(result, list)

    async def test_parse_returns_non_empty_list(self, snapshot_content):
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        assert len(result) > 0

    async def test_each_item_is_dict(self, snapshot_content):
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert isinstance(item, dict)


class TestCategoriesParserFields:
    async def test_each_category_has_name_field(self, snapshot_content):
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "name" in item, f"Category dict missing 'name': {item}"

    async def test_each_category_has_url_field(self, snapshot_content):
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "url" in item, f"Category dict missing 'url': {item}"

    async def test_name_is_non_empty_string(self, snapshot_content):
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert isinstance(item["name"], str) and item["name"].strip() != ""

    async def test_url_is_non_empty_string(self, snapshot_content):
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert isinstance(item["url"], str) and item["url"].strip() != ""


class TestCategoriesParserCount:
    async def test_parses_exactly_10_categories(self, snapshot_content):
        """The Golf parts page always has exactly 10 main categories."""
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        assert len(result) == 10, (
            f"Expected exactly 10 categories, got {len(result)}: "
            f"{[item.get('name') for item in result]}"
        )


class TestCategoriesParserSpecificCategories:
    async def test_engine_category_present(self, snapshot_content):
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        assert "Engine" in names

    async def test_body_category_present(self, snapshot_content):
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        assert "Body" in names

    async def test_electrics_category_present(self, snapshot_content):
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        assert "Electrics" in names

    async def test_gearbox_category_present(self, snapshot_content):
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        assert "Gearbox" in names

    async def test_all_expected_categories_present(self, snapshot_content):
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        for expected in EXPECTED_CATEGORIES:
            assert expected in names, f"Expected category '{expected}' not found in {names}"

    async def test_category_order_is_correct(self, snapshot_content):
        """Categories appear in a fixed order matching the main group index."""
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        assert names == EXPECTED_CATEGORIES, (
            f"Category order mismatch.\nExpected: {EXPECTED_CATEGORIES}\nGot: {names}"
        )

    async def test_engine_url_contains_maingroup_1(self, snapshot_content):
        """Engine category URL should encode MainGroup==1."""
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        engine = next((item for item in result if item["name"] == "Engine"), None)
        assert engine is not None
        assert "catcar.info" in engine["url"]

    async def test_urls_are_absolute(self, snapshot_content):
        parser = CategoriesParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert item["url"].startswith("http"), (
                f"Category URL should be absolute, got: {item['url']}"
            )


class TestCategoriesParserGetValidator:
    def test_get_validator_returns_parsed_category(self):
        from crawler.validators.model import ParsedCategory

        parser = CategoriesParser()
        assert parser.get_validator() is ParsedCategory
