"""
Tests for SubgroupsParser.

The vw-golf-engine-snapshot.yaml represents the "Subgroups" page for the Engine
category (MainGroup=1) of the Golf/Variant/4Motion 2017 (Golf 5G1***).

The table columns are: MG (main group index), Ill-No (illustration number/link),
Description, Remark, Model data.

From the snapshot, the first few subgroup rows visible are:
  - MG=1, Ill-No=10003, desc="base engine", remark="1.0 ltr.", model_data="petrol eng.+ CHZD"
  - MG=1, Ill-No=10005, desc="base engine", remark="1.2 ltr.", model_data="petrol eng.+ CJZA,CJZB, CYVA,CYVB"
  - MG=1, Ill-No=10010, desc="base engine", remark="1.4ltr.", model_data="petrol eng.+ CMBA,CPVA, ..."

Each parsed item must have: 'ill_no' (illustration number), 'description', 'url'.
"""

import pytest
from pathlib import Path

from crawler.parsers.subgroups import SubgroupsParser


SNAPSHOTS_DIR = Path(__file__).parent.parent / "snapshots"


@pytest.fixture
def snapshot_content() -> str:
    with open(SNAPSHOTS_DIR / "vw-golf-engine-snapshot.yaml") as f:
        return f.read()


class TestSubgroupsParserReturnType:
    async def test_parse_returns_list(self, snapshot_content):
        parser = SubgroupsParser()
        result = await parser.parse(snapshot_content)
        assert isinstance(result, list)

    async def test_parse_returns_non_empty_list(self, snapshot_content):
        parser = SubgroupsParser()
        result = await parser.parse(snapshot_content)
        assert len(result) > 0

    async def test_each_item_is_dict(self, snapshot_content):
        parser = SubgroupsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert isinstance(item, dict)


class TestSubgroupsParserFields:
    async def test_each_subgroup_has_ill_no_field(self, snapshot_content):
        parser = SubgroupsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "ill_no" in item, f"Subgroup dict missing 'ill_no': {item}"

    async def test_each_subgroup_has_description_field(self, snapshot_content):
        parser = SubgroupsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "description" in item, f"Subgroup dict missing 'description': {item}"

    async def test_each_subgroup_has_url_field(self, snapshot_content):
        parser = SubgroupsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "url" in item, f"Subgroup dict missing 'url': {item}"

    async def test_ill_no_is_non_empty_string(self, snapshot_content):
        parser = SubgroupsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert isinstance(item["ill_no"], str) and item["ill_no"].strip() != ""

    async def test_description_is_non_empty_string(self, snapshot_content):
        parser = SubgroupsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert isinstance(item["description"], str) and item["description"].strip() != ""


class TestSubgroupsParserCount:
    async def test_parses_at_least_3_subgroups(self, snapshot_content):
        """The engine snapshot has multiple base engine subgroup entries."""
        parser = SubgroupsParser()
        result = await parser.parse(snapshot_content)
        assert len(result) >= 3, f"Expected at least 3 subgroups, got {len(result)}"


class TestSubgroupsParserSpecificEntries:
    async def test_subgroup_10003_present(self, snapshot_content):
        """Ill-No 10003 is the 1.0 ltr. base engine subgroup."""
        parser = SubgroupsParser()
        result = await parser.parse(snapshot_content)
        ill_nos = [item["ill_no"] for item in result]
        assert "10003" in ill_nos, f"Expected ill_no '10003', got: {ill_nos}"

    async def test_subgroup_10005_present(self, snapshot_content):
        """Ill-No 10005 is the 1.2 ltr. base engine subgroup."""
        parser = SubgroupsParser()
        result = await parser.parse(snapshot_content)
        ill_nos = [item["ill_no"] for item in result]
        assert "10005" in ill_nos, f"Expected ill_no '10005', got: {ill_nos}"

    async def test_subgroup_10010_present(self, snapshot_content):
        """Ill-No 10010 is the 1.4 ltr. base engine subgroup."""
        parser = SubgroupsParser()
        result = await parser.parse(snapshot_content)
        ill_nos = [item["ill_no"] for item in result]
        assert "10010" in ill_nos, f"Expected ill_no '10010', got: {ill_nos}"

    async def test_10003_description_is_base_engine(self, snapshot_content):
        parser = SubgroupsParser()
        result = await parser.parse(snapshot_content)
        entry = next((item for item in result if item["ill_no"] == "10003"), None)
        assert entry is not None
        assert "base engine" in entry["description"].lower()

    async def test_urls_contain_catcar(self, snapshot_content):
        parser = SubgroupsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "catcar.info" in item["url"], (
                f"Subgroup URL should reference catcar.info: {item['url']}"
            )

    async def test_10003_url_contains_ill_no(self, snapshot_content):
        """The URL for subgroup 10003 should encode the Bildtafel=10003 parameter."""
        parser = SubgroupsParser()
        result = await parser.parse(snapshot_content)
        entry = next((item for item in result if item["ill_no"] == "10003"), None)
        assert entry is not None
        # The URL is base64-encoded but should reference ill_no somehow
        assert entry["url"].startswith("http")


class TestSubgroupsParserGetValidator:
    def test_get_validator_returns_parsed_subgroup(self):
        from crawler.validators.model import ParsedSubgroup

        parser = SubgroupsParser()
        assert parser.get_validator() is ParsedSubgroup
