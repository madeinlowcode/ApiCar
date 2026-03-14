"""
Tests for ModelYearsParser.

The vw-golf-variants-snapshot.yaml shows the year/variant selection page for
Golf/Variant/4Motion (Europe). The table columns are: Model, Year, Restriction.

Years present in the snapshot: 1998 through 2019 (inclusive), but some years
appear multiple times with different restrictions/variants. For example:
  - 2004 appears twice (1J-4-000 001 >> and 1K-4-000 001 >>)
  - 2005 appears three times
  - 2007 appears twice (Golf, Golf Variant)
  - 2009 appears three times
  - etc.

Unique years: 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007,
              2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019
That is 22 unique years. Total rows: ~38

Each parsed item must have at minimum: 'year', 'url', and optionally 'restriction'.
"""

import pytest
from pathlib import Path

from crawler.parsers.model_years import ModelYearsParser


SNAPSHOTS_DIR = Path(__file__).parent.parent / "snapshots"


@pytest.fixture
def snapshot_content() -> str:
    with open(SNAPSHOTS_DIR / "vw-golf-variants-snapshot.yaml") as f:
        return f.read()


class TestModelYearsParserReturnType:
    async def test_parse_returns_list(self, snapshot_content):
        parser = ModelYearsParser()
        result = await parser.parse(snapshot_content)
        assert isinstance(result, list)

    async def test_parse_returns_non_empty_list(self, snapshot_content):
        parser = ModelYearsParser()
        result = await parser.parse(snapshot_content)
        assert len(result) > 0

    async def test_each_item_is_dict(self, snapshot_content):
        parser = ModelYearsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert isinstance(item, dict)


class TestModelYearsParserFields:
    async def test_each_year_entry_has_year_field(self, snapshot_content):
        parser = ModelYearsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "year" in item, f"Year entry missing 'year' key: {item}"

    async def test_each_year_entry_has_url_field(self, snapshot_content):
        parser = ModelYearsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "url" in item, f"Year entry missing 'url' key: {item}"

    async def test_year_field_is_integer_or_string_digit(self, snapshot_content):
        parser = ModelYearsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            year = item["year"]
            assert str(year).isdigit(), f"Year must be a digit string or int, got: {year}"

    async def test_year_values_in_valid_range(self, snapshot_content):
        parser = ModelYearsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            year = int(item["year"])
            assert 1990 <= year <= 2030, f"Year {year} out of expected range"


class TestModelYearsParserYearCount:
    async def test_parses_at_least_22_unique_years(self, snapshot_content):
        """The Golf variants snapshot covers years 1998-2019: 22 unique years."""
        parser = ModelYearsParser()
        result = await parser.parse(snapshot_content)
        unique_years = {str(item["year"]) for item in result}
        assert len(unique_years) >= 22, (
            f"Expected at least 22 unique years, got {len(unique_years)}: {sorted(unique_years)}"
        )

    async def test_total_rows_at_least_30(self, snapshot_content):
        """Multiple variants per year means total rows exceed 30."""
        parser = ModelYearsParser()
        result = await parser.parse(snapshot_content)
        assert len(result) >= 30, f"Expected at least 30 rows, got {len(result)}"


class TestModelYearsParserSpecificYears:
    async def test_year_1998_present(self, snapshot_content):
        parser = ModelYearsParser()
        result = await parser.parse(snapshot_content)
        years = [str(item["year"]) for item in result]
        assert "1998" in years

    async def test_year_2019_present(self, snapshot_content):
        parser = ModelYearsParser()
        result = await parser.parse(snapshot_content)
        years = [str(item["year"]) for item in result]
        assert "2019" in years

    async def test_year_2004_appears_multiple_times(self, snapshot_content):
        """2004 has two entries with different chassis restrictions."""
        parser = ModelYearsParser()
        result = await parser.parse(snapshot_content)
        year_2004 = [item for item in result if str(item["year"]) == "2004"]
        assert len(year_2004) >= 2, (
            f"Expected at least 2 entries for year 2004, got {len(year_2004)}"
        )

    async def test_year_1998_has_restriction(self, snapshot_content):
        """Year 1998 entry has restriction '1J-W-000 001 >>'."""
        parser = ModelYearsParser()
        result = await parser.parse(snapshot_content)
        entry_1998 = next((item for item in result if str(item["year"]) == "1998"), None)
        assert entry_1998 is not None
        restriction = entry_1998.get("restriction", "")
        assert "1J" in restriction, (
            f"Expected restriction containing '1J' for 1998, got: '{restriction}'"
        )

    async def test_urls_contain_catcar(self, snapshot_content):
        parser = ModelYearsParser()
        result = await parser.parse(snapshot_content)
        for item in result:
            assert "catcar.info" in item["url"], (
                f"URL should reference catcar.info: {item['url']}"
            )


class TestModelYearsParserGetValidator:
    def test_get_validator_returns_parsed_model_year(self):
        from crawler.validators.model import ParsedModelYear

        parser = ModelYearsParser()
        assert parser.get_validator() is ParsedModelYear
