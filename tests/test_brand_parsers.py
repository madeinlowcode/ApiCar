"""Tests for brand navigation parsers against real HTML fixtures."""
import os
import pytest

from crawler.parsers.brand_navigation import (
    parse_year_tabs,
    parse_region_links,
    parse_table_links,
    parse_groups_parts_links,
    detect_and_parse,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "brands")


def _load(filename: str) -> str:
    with open(os.path.join(FIXTURES_DIR, filename), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# parse_year_tabs
# ---------------------------------------------------------------------------

class TestParseYearTabs:

    def test_honda_homepage_has_years(self):
        html = _load("honda_homepage.html")
        result = parse_year_tabs(html)
        assert len(result) > 10
        years = [r["year"] for r in result]
        assert "2011" in years

    def test_honda_homepage_urls_contain_catcar(self):
        html = _load("honda_homepage.html")
        result = parse_year_tabs(html)
        for item in result:
            assert "catcar.info" in item["url"]

    def test_honda_homepage_no_duplicate_urls(self):
        html = _load("honda_homepage.html")
        result = parse_year_tabs(html)
        urls = [r["url"] for r in result]
        assert len(urls) == len(set(urls))

    def test_kia_homepage_has_years(self):
        html = _load("kia_homepage.html")
        result = parse_year_tabs(html)
        assert len(result) > 10
        years = [r["year"] for r in result]
        assert "2018" in years

    def test_hyundai_homepage_has_years(self):
        html = _load("hyundai_homepage.html")
        result = parse_year_tabs(html)
        assert len(result) > 10
        years = [r["year"] for r in result]
        assert "2018" in years

    def test_chrysler_homepage_has_years(self):
        html = _load("chrysler_homepage.html")
        result = parse_year_tabs(html)
        assert len(result) > 5
        years = [r["year"] for r in result]
        assert "2017" in years

    def test_nissan_homepage_returns_empty(self):
        html = _load("nissan_homepage.html")
        result = parse_year_tabs(html)
        assert result == []

    def test_mazda_homepage_returns_empty(self):
        html = _load("mazda_homepage.html")
        result = parse_year_tabs(html)
        assert result == []

    def test_subaru_homepage_returns_empty(self):
        html = _load("subaru_homepage.html")
        result = parse_year_tabs(html)
        assert result == []

    def test_honda_year_page_has_years(self):
        html = _load("honda_year.html")
        result = parse_year_tabs(html)
        assert len(result) > 10

    def test_kia_year_page_has_years(self):
        html = _load("kia_year.html")
        result = parse_year_tabs(html)
        assert len(result) > 10


# ---------------------------------------------------------------------------
# parse_region_links
# ---------------------------------------------------------------------------

class TestParseRegionLinks:

    def test_nissan_homepage_has_regions(self):
        html = _load("nissan_homepage.html")
        result = parse_region_links(html)
        assert len(result) >= 4
        names = [r["name"] for r in result]
        assert any("Europe" in n for n in names)

    def test_nissan_homepage_urls_contain_catcar(self):
        html = _load("nissan_homepage.html")
        result = parse_region_links(html)
        for item in result:
            assert "catcar.info" in item["url"]

    def test_mazda_homepage_has_markets(self):
        html = _load("mazda_homepage.html")
        result = parse_region_links(html)
        assert len(result) >= 3
        names = [r["name"] for r in result]
        assert "Europe" in names

    def test_subaru_homepage_has_regions(self):
        html = _load("subaru_homepage.html")
        result = parse_region_links(html)
        assert len(result) >= 3
        names = [r["name"] for r in result]
        assert any("Europe" in n for n in names)

    def test_kia_homepage_table_regions(self):
        """Kia homepage has region links inside table cells after year tabs."""
        html = _load("kia_homepage.html")
        result = parse_region_links(html)
        assert len(result) >= 4
        names = [r["name"] for r in result]
        assert "Europe" in names

    def test_honda_homepage_no_regions(self):
        """Honda homepage has no region/market links."""
        html = _load("honda_homepage.html")
        result = parse_region_links(html)
        assert result == []

    def test_no_duplicate_urls(self):
        html = _load("nissan_homepage.html")
        result = parse_region_links(html)
        urls = [r["url"] for r in result]
        assert len(urls) == len(set(urls))

    def test_chrysler_market_has_markets(self):
        """Chrysler market page has market links inside over-layer list."""
        html = _load("chrysler_market.html")
        result = parse_region_links(html)
        assert len(result) >= 1
        names = [r["name"] for r in result]
        assert any("CANADA" in n or "EXPORT" in n or "US" in n for n in names)


# ---------------------------------------------------------------------------
# parse_table_links
# ---------------------------------------------------------------------------

class TestParseTableLinks:

    def test_honda_year_has_models(self):
        html = _load("honda_year.html")
        result = parse_table_links(html)
        assert len(result) >= 5
        names = [r["name"] for r in result]
        assert "ACCORD" in names

    def test_honda_year_urls_contain_catcar(self):
        html = _load("honda_year.html")
        result = parse_table_links(html)
        for item in result:
            assert "catcar.info" in item["url"]

    def test_nissan_region_has_models(self):
        html = _load("nissan_region.html")
        result = parse_table_links(html)
        assert len(result) >= 5

    def test_mazda_region_has_models(self):
        html = _load("mazda_region.html")
        result = parse_table_links(html)
        assert len(result) >= 5
        names = [r["name"] for r in result]
        assert "323" in names

    def test_subaru_region_has_models(self):
        html = _load("subaru_region.html")
        result = parse_table_links(html)
        assert len(result) >= 5
        names = [r["name"] for r in result]
        assert "LEGACY" in names

    def test_no_region_links_in_table(self):
        """Table links parser should not return links with region== or market==."""
        html = _load("nissan_homepage.html")
        result = parse_table_links(html)
        for item in result:
            assert "region==" not in item["url"]
            assert "market==" not in item["url"]

    def test_no_duplicate_urls(self):
        html = _load("honda_year.html")
        result = parse_table_links(html)
        urls = [r["url"] for r in result]
        assert len(urls) == len(set(urls))


# ---------------------------------------------------------------------------
# parse_groups_parts_links
# ---------------------------------------------------------------------------

class TestParseGroupsPartsLinks:

    def test_kia_region_models_has_items(self):
        html = _load("kia_region_models.html")
        result = parse_groups_parts_links(html)
        assert len(result) >= 3

    def test_kia_region_models_urls_contain_catcar(self):
        html = _load("kia_region_models.html")
        result = parse_groups_parts_links(html)
        for item in result:
            assert "catcar.info" in item["url"]

    def test_kia_categories_has_items(self):
        html = _load("kia_categories.html")
        result = parse_groups_parts_links(html)
        assert len(result) >= 5
        names = [r["name"] for r in result]
        assert "ENGINE" in names

    def test_kia_categories_all_items(self):
        html = _load("kia_categories.html")
        result = parse_groups_parts_links(html)
        names = [r["name"] for r in result]
        assert "TRANSMISSION" in names
        assert "CHASSIS" in names
        assert "BODY" in names

    def test_honda_homepage_no_groups_parts(self):
        html = _load("honda_homepage.html")
        result = parse_groups_parts_links(html)
        assert result == []

    def test_no_duplicate_urls(self):
        html = _load("kia_categories.html")
        result = parse_groups_parts_links(html)
        urls = [r["url"] for r in result]
        assert len(urls) == len(set(urls))


# ---------------------------------------------------------------------------
# detect_and_parse
# ---------------------------------------------------------------------------

class TestDetectAndParse:

    def test_honda_homepage_detected_as_years(self):
        html = _load("honda_homepage.html")
        result = detect_and_parse(html)
        assert result["type"] == "years"
        assert len(result["items"]) > 10

    def test_kia_homepage_detected_as_years(self):
        html = _load("kia_homepage.html")
        result = detect_and_parse(html)
        assert result["type"] == "years"

    def test_hyundai_homepage_detected_as_years(self):
        html = _load("hyundai_homepage.html")
        result = detect_and_parse(html)
        assert result["type"] == "years"

    def test_chrysler_homepage_detected_as_years(self):
        html = _load("chrysler_homepage.html")
        result = detect_and_parse(html)
        assert result["type"] == "years"

    def test_nissan_homepage_detected_as_regions(self):
        html = _load("nissan_homepage.html")
        result = detect_and_parse(html)
        assert result["type"] == "regions"
        assert len(result["items"]) >= 4

    def test_mazda_homepage_detected_as_regions(self):
        html = _load("mazda_homepage.html")
        result = detect_and_parse(html)
        assert result["type"] == "regions"

    def test_subaru_homepage_detected_as_regions(self):
        html = _load("subaru_homepage.html")
        result = detect_and_parse(html)
        assert result["type"] == "regions"

    def test_honda_year_detected_as_years(self):
        """Honda year page has both tabs and table; years take priority."""
        html = _load("honda_year.html")
        result = detect_and_parse(html)
        assert result["type"] == "years"

    def test_nissan_region_detected_as_table_links(self):
        html = _load("nissan_region.html")
        result = detect_and_parse(html)
        assert result["type"] == "table_links"

    def test_mazda_region_detected_as_table_links(self):
        html = _load("mazda_region.html")
        result = detect_and_parse(html)
        assert result["type"] == "table_links"

    def test_subaru_region_detected_as_table_links(self):
        html = _load("subaru_region.html")
        result = detect_and_parse(html)
        assert result["type"] == "table_links"

    def test_kia_region_models_detected_as_groups_parts(self):
        html = _load("kia_region_models.html")
        result = detect_and_parse(html)
        assert result["type"] == "groups_parts"

    def test_kia_categories_detected_as_groups_parts(self):
        html = _load("kia_categories.html")
        result = detect_and_parse(html)
        assert result["type"] == "groups_parts"

    def test_empty_html_detected_as_empty(self):
        result = detect_and_parse("<html><body></body></html>")
        assert result["type"] == "empty"
        assert result["items"] == []
