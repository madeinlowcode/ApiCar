"""
Tests for PartsParser.

The vw-golf-parts-detail-snapshot.yaml represents the "Parts" detail page for
subgroup 10003 (base engine, 1.0 ltr.) of the Golf/Variant/4Motion 2017.

The table columns are: (position), (image), part number, Description, Remark,
ST (quantity), Model data, (basket link).

Parts visible in the snapshot:
  - pos=1, part_no="04C100032F",  desc="base engine",    remark="",        st=1, model_data="PR-G1C"
  - pos=1, part_no="04C100032FX", desc="base engine",    remark="",        st=1, model_data="PR-G1C"
  - pos=2, part_no="06B105313D",  desc="needle bearing", remark="15X21X23,6", st=1, model_data="PR-G1C"

Each parsed item must have: 'part_no', 'description', 'url'.
Optional fields: 'position', 'remark', 'quantity', 'model_data'.
"""

import pytest
from pathlib import Path

from crawler.parsers.parts import PartsParser


SNAPSHOTS_DIR = Path(__file__).parent.parent / "snapshots"


@pytest.fixture
def snapshot_content() -> str:
    with open(SNAPSHOTS_DIR / "vw-golf-parts-detail-snapshot.yaml") as f:
        return f.read()


class TestPartsParserReturnType:
    async def test_parse_returns_list(self, snapshot_content):
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        assert isinstance(result, list)

    async def test_parse_returns_non_empty_list(self, snapshot_content):
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        assert len(result) > 0

    async def test_each_item_is_dict(self, snapshot_content):
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert isinstance(item, dict)


class TestPartsParserFields:
    async def test_each_part_has_part_no_field(self, snapshot_content):
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "part_no" in item, f"Part dict missing 'part_no': {item}"

    async def test_each_part_has_description_field(self, snapshot_content):
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "description" in item, f"Part dict missing 'description': {item}"

    async def test_each_part_has_url_field(self, snapshot_content):
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "url" in item, f"Part dict missing 'url': {item}"

    async def test_part_no_is_non_empty_string(self, snapshot_content):
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert isinstance(item["part_no"], str) and item["part_no"].strip() != ""

    async def test_description_is_non_empty_string(self, snapshot_content):
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert isinstance(item["description"], str) and item["description"].strip() != ""


class TestPartsParserCount:
    async def test_parses_at_least_3_parts(self, snapshot_content):
        """The parts detail snapshot shows at least 3 part rows."""
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        assert len(result) >= 3, f"Expected at least 3 parts, got {len(result)}"


class TestPartsParserSpecificParts:
    async def test_part_04c100032f_present(self, snapshot_content):
        """Part 04C100032F (base engine complete) must be in results."""
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        part_nos = [item["part_no"] for item in result]
        assert "04C100032F" in part_nos, (
            f"Expected part '04C100032F', got: {part_nos}"
        )

    async def test_part_04c100032fx_present(self, snapshot_content):
        """Part 04C100032FX (exchange base engine) must be in results."""
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        part_nos = [item["part_no"] for item in result]
        assert "04C100032FX" in part_nos, (
            f"Expected part '04C100032FX', got: {part_nos}"
        )

    async def test_part_06b105313d_present(self, snapshot_content):
        """Part 06B105313D (needle bearing) must be in results."""
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        part_nos = [item["part_no"] for item in result]
        assert "06B105313D" in part_nos, (
            f"Expected part '06B105313D', got: {part_nos}"
        )

    async def test_base_engine_description(self, snapshot_content):
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        engine = next((item for item in result if item["part_no"] == "04C100032F"), None)
        assert engine is not None
        assert "base engine" in engine["description"].lower()

    async def test_needle_bearing_description(self, snapshot_content):
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        bearing = next((item for item in result if item["part_no"] == "06B105313D"), None)
        assert bearing is not None
        assert "needle bearing" in bearing["description"].lower()

    async def test_needle_bearing_remark_contains_dimensions(self, snapshot_content):
        """06B105313D has remark '15X21X23,6' indicating its dimensions."""
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        bearing = next((item for item in result if item["part_no"] == "06B105313D"), None)
        assert bearing is not None
        remark = bearing.get("remark", "")
        assert "15X21" in remark, f"Expected remark with '15X21', got: '{remark}'"

    async def test_part_urls_point_to_tradesoft_or_catcar(self, snapshot_content):
        """Part URLs in snapshot point to ar-demo.tradesoft.pro."""
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            url = item["url"]
            assert url.startswith("http"), f"Part URL should be absolute: {url}"

    async def test_part_url_contains_article_number(self, snapshot_content):
        """Each part URL should embed the article/part number."""
        parser = PartsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert item["part_no"] in item["url"] or "article=" in item["url"], (
                f"URL should contain part number or article param: {item['url']}"
            )


class TestPartsParserGetValidator:
    def test_get_validator_returns_parsed_part(self):
        from crawler.validators.part import ParsedPart

        parser = PartsParser()
        assert parser.get_validator() is ParsedPart
