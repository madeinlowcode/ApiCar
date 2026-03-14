"""
Tests for HomepageParser.

The homepage snapshot contains car brand links organized by region (Europe, Japan,
Korea, USA). Each brand entry has a name and a URL. The parser is expected to return
a list of dicts, one per brand, with at minimum 'name' and 'url' keys.

Brands present in the snapshot (Europe section):
  Audi, Seat, Skoda, Volkswagen, BMW, Mini, Rolls-Royce, Mercedes, Smart,
  Renault, Dacia, Ford, Peugeot, Opel, Vauxhall, Citroёn, Volvo, Jaguar

Japan section: Infiniti, Nissan, Lexus, Toyota, Honda, Suzuki, Mazda,
               Mitsubishi, Isuzu, Subaru

Korea section: Hyundai, Kia, Ssang Yong

USA section: Chrysler

Total distinct brand names visible in the main listing: 28
"""

import pytest
import yaml
from pathlib import Path

from crawler.parsers.homepage import HomepageParser


SNAPSHOTS_DIR = Path(__file__).parent.parent / "snapshots"


@pytest.fixture
def snapshot_content() -> str:
    with open(SNAPSHOTS_DIR / "homepage-snapshot.yaml") as f:
        return f.read()


class TestHomepageParserReturnType:
    async def test_parse_returns_list(self, snapshot_content):
        parser = HomepageParser()
        result = await parser.parse(snapshot_content)
        assert isinstance(result, list), "parse() must return a list"

    async def test_parse_returns_list_of_dicts(self, snapshot_content):
        parser = HomepageParser()
        result = await parser.parse(snapshot_content)
        assert len(result) > 0, "parse() must not return an empty list"
        for item in result:
            assert isinstance(item, dict), "Each item must be a dict"


class TestHomepageParserBrandFields:
    async def test_each_brand_has_name_field(self, snapshot_content):
        parser = HomepageParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "name" in item, f"Brand dict missing 'name' key: {item}"

    async def test_each_brand_has_url_field(self, snapshot_content):
        parser = HomepageParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "url" in item, f"Brand dict missing 'url' key: {item}"

    async def test_brand_names_are_non_empty_strings(self, snapshot_content):
        parser = HomepageParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert isinstance(item["name"], str), "Brand name must be a string"
            assert item["name"].strip() != "", "Brand name must not be empty"

    async def test_brand_urls_are_non_empty_strings(self, snapshot_content):
        parser = HomepageParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert isinstance(item["url"], str), "Brand url must be a string"
            assert item["url"].strip() != "", "Brand url must not be empty"


class TestHomepageParserBrandCount:
    async def test_parses_at_least_28_brands(self, snapshot_content):
        """The snapshot lists 28 distinct brand names in the main brand grid."""
        parser = HomepageParser()
        result = await parser.parse(snapshot_content)
        assert len(result) >= 28, (
            f"Expected at least 28 brands, got {len(result)}"
        )


class TestHomepageParserSpecificBrands:
    async def test_volkswagen_brand_present(self, snapshot_content):
        parser = HomepageParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        assert "Volkswagen" in names, "Volkswagen must be in parsed brands"

    async def test_audi_brand_present(self, snapshot_content):
        parser = HomepageParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        assert "Audi" in names, "Audi must be in parsed brands"

    async def test_toyota_brand_present(self, snapshot_content):
        parser = HomepageParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        assert "Toyota" in names, "Toyota must be in parsed brands"

    async def test_bmw_brand_present(self, snapshot_content):
        parser = HomepageParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        assert "BMW" in names, "BMW must be in parsed brands"

    async def test_hyundai_brand_present(self, snapshot_content):
        parser = HomepageParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        assert "Hyundai" in names, "Hyundai must be in parsed brands"

    async def test_chrysler_brand_present(self, snapshot_content):
        parser = HomepageParser()
        result = await parser.parse(snapshot_content)
        names = [item["name"] for item in result]
        assert "Chrysler" in names, "Chrysler must be in parsed brands"

    async def test_volkswagen_url_contains_audivw(self, snapshot_content):
        """Volkswagen's URL should point to /audivw/ catalog."""
        parser = HomepageParser()
        result = await parser.parse(snapshot_content)
        vw = next((item for item in result if item["name"] == "Volkswagen"), None)
        assert vw is not None
        assert "audivw" in vw["url"], (
            f"Volkswagen URL should contain 'audivw', got: {vw['url']}"
        )

    async def test_bmw_url_contains_bmw(self, snapshot_content):
        parser = HomepageParser()
        result = await parser.parse(snapshot_content)
        bmw = next((item for item in result if item["name"] == "BMW"), None)
        assert bmw is not None
        assert "bmw" in bmw["url"], f"BMW URL should contain 'bmw', got: {bmw['url']}"


class TestHomepageParserGetValidator:
    def test_get_validator_returns_class(self):
        from crawler.validators.brand import ParsedBrand

        parser = HomepageParser()
        validator = parser.get_validator()
        assert validator is ParsedBrand
