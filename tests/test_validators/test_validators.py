"""
Tests for all Pydantic validators used by the crawler parsers.

These tests verify:
1. Valid data matching the snapshot structure passes validation
2. Invalid data (empty strings, None, wrong types, missing required fields) raises
   ValidationError
3. Edge cases: special characters in names, very long strings, Unicode

All validators are currently stubs (empty models), so every test that checks for
required fields or type enforcement will FAIL in the red phase.
"""

import pytest
from pydantic import ValidationError

from crawler.validators.brand import ParsedBrand
from crawler.validators.model import ParsedModel, ParsedModelYear, ParsedCategory, ParsedSubgroup
from crawler.validators.part import ParsedPart


# ---------------------------------------------------------------------------
# ParsedBrand tests
# ---------------------------------------------------------------------------

class TestParsedBrandValidData:
    def test_valid_brand_with_name_and_url(self):
        brand = ParsedBrand(name="Volkswagen", url="/audivw/?lang=en")
        assert brand.name == "Volkswagen"
        assert brand.url == "/audivw/?lang=en"

    def test_valid_brand_audi(self):
        brand = ParsedBrand(
            name="Audi",
            url="/audivw/?lang=en&l=c3RzPT17IjEwIjoiQnJhbmQiLCIyMCI6IkFVREkifQ%3D%3D",
        )
        assert brand.name == "Audi"

    def test_valid_brand_with_special_char_in_name(self):
        """Citroёn has a special Cyrillic 'ё' character in the snapshot."""
        brand = ParsedBrand(name="Citroёn", url="/citroen/?lang=en")
        assert brand.name == "Citroёn"

    def test_valid_brand_ssang_yong(self):
        """Brand names can contain spaces."""
        brand = ParsedBrand(name="Ssang Yong", url="/ssangyong/?lang=en")
        assert brand.name == "Ssang Yong"

    def test_valid_brand_rolls_royce(self):
        """Brand names can contain hyphens."""
        brand = ParsedBrand(name="Rolls-Royce", url="/bmw/?lang=en&l=abc")
        assert brand.name == "Rolls-Royce"


class TestParsedBrandInvalidData:
    def test_missing_name_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ParsedBrand(url="/audivw/?lang=en")

    def test_missing_url_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ParsedBrand(name="Volkswagen")

    def test_empty_name_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ParsedBrand(name="", url="/audivw/?lang=en")

    def test_empty_url_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ParsedBrand(name="Volkswagen", url="")

    def test_none_name_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ParsedBrand(name=None, url="/audivw/?lang=en")

    def test_none_url_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ParsedBrand(name="Volkswagen", url=None)

    def test_whitespace_only_name_raises_validation_error(self):
        with pytest.raises(ValidationError):
            ParsedBrand(name="   ", url="/audivw/?lang=en")


# ---------------------------------------------------------------------------
# ParsedModel tests
# ---------------------------------------------------------------------------

class TestParsedModelValidData:
    def test_valid_model_golf(self):
        model = ParsedModel(
            code="GO",
            name="Golf",
            url="http://catcar.info/audivw/?lang=en&l=abc123",
            production_date="1975-1998",
        )
        assert model.code == "GO"
        assert model.name == "Golf"

    def test_valid_model_golf_variant(self):
        model = ParsedModel(
            code="GOLF",
            name="Golf/Variant/4Motion",
            url="http://catcar.info/audivw/?lang=en&l=xyz",
            production_date="1998-...",
        )
        assert model.name == "Golf/Variant/4Motion"

    def test_valid_model_with_description(self):
        model = ParsedModel(
            code="GL",
            name="Gol",
            url="http://catcar.info/audivw/?lang=en&l=abc",
            production_date="2004-2011",
            description="BR",
        )
        assert model.description == "BR"

    def test_open_ended_production_date(self):
        """Models still in production have date ending in '...'"""
        model = ParsedModel(
            code="TIG",
            name="Tiguan",
            url="http://catcar.info/audivw/?lang=en&l=abc",
            production_date="2008-...",
        )
        assert "..." in model.production_date

    def test_valid_model_markets_field(self):
        model = ParsedModel(
            code="PA",
            name="Passat/Variant/Santana",
            url="http://catcar.info/audivw/?lang=en&l=abc",
            production_date="1974-...",
            markets="A;B;C;D;E;G;L;P;S;W;X;Y;Z;9",
        )
        assert ";" in model.markets


class TestParsedModelInvalidData:
    def test_missing_code_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedModel(
                name="Golf",
                url="http://catcar.info/audivw/?lang=en&l=abc",
                production_date="1975-1998",
            )

    def test_missing_name_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedModel(
                code="GO",
                url="http://catcar.info/audivw/?lang=en&l=abc",
                production_date="1975-1998",
            )

    def test_missing_url_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedModel(
                code="GO",
                name="Golf",
                production_date="1975-1998",
            )

    def test_missing_production_date_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedModel(
                code="GO",
                name="Golf",
                url="http://catcar.info/audivw/?lang=en&l=abc",
            )

    def test_empty_code_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedModel(
                code="",
                name="Golf",
                url="http://catcar.info/audivw/?lang=en&l=abc",
                production_date="1975-1998",
            )

    def test_empty_name_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedModel(
                code="GO",
                name="",
                url="http://catcar.info/audivw/?lang=en&l=abc",
                production_date="1975-1998",
            )


# ---------------------------------------------------------------------------
# ParsedModelYear tests
# ---------------------------------------------------------------------------

class TestParsedModelYearValidData:
    def test_valid_year_1998_with_restriction(self):
        year = ParsedModelYear(
            year=1998,
            url="http://catcar.info/audivw/?lang=en&l=abc",
            restriction="1J-W-000 001 >>",
        )
        assert year.year == 1998
        assert year.restriction == "1J-W-000 001 >>"

    def test_valid_year_1999_no_restriction(self):
        year = ParsedModelYear(
            year=1999,
            url="http://catcar.info/audivw/?lang=en&l=abc",
        )
        assert year.year == 1999

    def test_valid_year_2017_with_variant(self):
        year = ParsedModelYear(
            year=2017,
            url="http://catcar.info/audivw/?lang=en&l=abc",
            restriction="Golf BQ1***/Golf Variant BV5***",
        )
        assert year.year == 2017

    def test_year_can_be_string_digit(self):
        """Year may be provided as a string from parsed HTML."""
        year = ParsedModelYear(
            year="2013",
            url="http://catcar.info/audivw/?lang=en&l=abc",
        )
        assert int(year.year) == 2013


class TestParsedModelYearInvalidData:
    def test_missing_year_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedModelYear(url="http://catcar.info/audivw/?lang=en&l=abc")

    def test_missing_url_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedModelYear(year=2017)

    def test_empty_url_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedModelYear(year=2017, url="")

    def test_non_numeric_year_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedModelYear(year="not-a-year", url="http://catcar.info/audivw/?lang=en&l=abc")

    def test_year_too_old_raises_error(self):
        """Years before 1900 are nonsensical for car catalogs."""
        with pytest.raises(ValidationError):
            ParsedModelYear(year=1800, url="http://catcar.info/audivw/?lang=en&l=abc")

    def test_year_in_far_future_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedModelYear(year=3000, url="http://catcar.info/audivw/?lang=en&l=abc")


# ---------------------------------------------------------------------------
# ParsedCategory tests
# ---------------------------------------------------------------------------

class TestParsedCategoryValidData:
    def test_valid_engine_category(self):
        cat = ParsedCategory(name="Engine", url="http://catcar.info/audivw/?lang=en&l=abc")
        assert cat.name == "Engine"

    def test_valid_category_with_comma_in_name(self):
        """'Fuel, exhaust, cooling' has commas."""
        cat = ParsedCategory(
            name="Fuel, exhaust, cooling",
            url="http://catcar.info/audivw/?lang=en&l=abc",
        )
        assert cat.name == "Fuel, exhaust, cooling"

    def test_valid_category_front_axle(self):
        cat = ParsedCategory(
            name="Front axle, steering",
            url="http://catcar.info/audivw/?lang=en&l=abc",
        )
        assert cat.name == "Front axle, steering"

    def test_valid_category_wheels_brakes(self):
        cat = ParsedCategory(
            name="Wheels, brakes",
            url="http://catcar.info/audivw/?lang=en&l=abc",
        )
        assert cat.name == "Wheels, brakes"


class TestParsedCategoryInvalidData:
    def test_missing_name_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedCategory(url="http://catcar.info/audivw/?lang=en&l=abc")

    def test_missing_url_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedCategory(name="Engine")

    def test_empty_name_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedCategory(name="", url="http://catcar.info/audivw/?lang=en&l=abc")

    def test_empty_url_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedCategory(name="Engine", url="")

    def test_none_name_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedCategory(name=None, url="http://catcar.info/audivw/?lang=en&l=abc")


# ---------------------------------------------------------------------------
# ParsedSubgroup tests
# ---------------------------------------------------------------------------

class TestParsedSubgroupValidData:
    def test_valid_subgroup_10003(self):
        sg = ParsedSubgroup(
            ill_no="10003",
            description="base engine",
            url="http://catcar.info/audivw/?lang=en&l=abc",
            remark="1.0 ltr.",
            model_data="petrol eng.+ CHZD",
        )
        assert sg.ill_no == "10003"
        assert sg.description == "base engine"

    def test_valid_subgroup_10005(self):
        sg = ParsedSubgroup(
            ill_no="10005",
            description="base engine",
            url="http://catcar.info/audivw/?lang=en&l=abc",
            remark="1.2 ltr.",
            model_data="petrol eng.+ CJZA,CJZB, CYVA,CYVB",
        )
        assert sg.ill_no == "10005"

    def test_subgroup_without_optional_fields(self):
        sg = ParsedSubgroup(
            ill_no="10010",
            description="base engine",
            url="http://catcar.info/audivw/?lang=en&l=abc",
        )
        assert sg.ill_no == "10010"


class TestParsedSubgroupInvalidData:
    def test_missing_ill_no_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedSubgroup(
                description="base engine",
                url="http://catcar.info/audivw/?lang=en&l=abc",
            )

    def test_missing_description_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedSubgroup(
                ill_no="10003",
                url="http://catcar.info/audivw/?lang=en&l=abc",
            )

    def test_missing_url_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedSubgroup(ill_no="10003", description="base engine")

    def test_empty_ill_no_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedSubgroup(
                ill_no="",
                description="base engine",
                url="http://catcar.info/audivw/?lang=en&l=abc",
            )

    def test_empty_description_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedSubgroup(
                ill_no="10003",
                description="",
                url="http://catcar.info/audivw/?lang=en&l=abc",
            )


# ---------------------------------------------------------------------------
# ParsedPart tests
# ---------------------------------------------------------------------------

class TestParsedPartValidData:
    def test_valid_part_04c100032f(self):
        part = ParsedPart(
            part_no="04C100032F",
            description="base engine",
            url="http://ar-demo.tradesoft.pro/search.html?article=04C100032F",
            position=1,
            quantity=1,
            model_data="PR-G1C",
        )
        assert part.part_no == "04C100032F"
        assert part.description == "base engine"

    def test_valid_part_04c100032fx(self):
        part = ParsedPart(
            part_no="04C100032FX",
            description="base engine",
            url="http://ar-demo.tradesoft.pro/search.html?article=04C100032FX",
            position=1,
            quantity=1,
            model_data="PR-G1C",
        )
        assert part.part_no == "04C100032FX"

    def test_valid_part_06b105313d_with_remark(self):
        part = ParsedPart(
            part_no="06B105313D",
            description="needle bearing",
            url="http://ar-demo.tradesoft.pro/search.html?article=06B105313D",
            position=2,
            remark="15X21X23,6",
            quantity=1,
            model_data="PR-G1C",
        )
        assert part.part_no == "06B105313D"
        assert part.remark == "15X21X23,6"

    def test_valid_part_without_optional_fields(self):
        part = ParsedPart(
            part_no="04C100032F",
            description="base engine",
            url="http://ar-demo.tradesoft.pro/search.html?article=04C100032F",
        )
        assert part.part_no == "04C100032F"

    def test_part_no_with_alphanumeric(self):
        """Part numbers contain uppercase letters and digits."""
        part = ParsedPart(
            part_no="06B105313D",
            description="needle bearing",
            url="http://ar-demo.tradesoft.pro/search.html?article=06B105313D",
        )
        assert part.part_no == "06B105313D"


class TestParsedPartInvalidData:
    def test_missing_part_no_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedPart(
                description="base engine",
                url="http://ar-demo.tradesoft.pro/search.html?article=04C100032F",
            )

    def test_missing_description_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedPart(
                part_no="04C100032F",
                url="http://ar-demo.tradesoft.pro/search.html?article=04C100032F",
            )

    def test_missing_url_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedPart(part_no="04C100032F", description="base engine")

    def test_empty_part_no_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedPart(
                part_no="",
                description="base engine",
                url="http://ar-demo.tradesoft.pro/search.html?article=04C100032F",
            )

    def test_empty_description_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedPart(
                part_no="04C100032F",
                description="",
                url="http://ar-demo.tradesoft.pro/search.html?article=04C100032F",
            )

    def test_empty_url_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedPart(part_no="04C100032F", description="base engine", url="")

    def test_none_part_no_raises_error(self):
        with pytest.raises(ValidationError):
            ParsedPart(
                part_no=None,
                description="base engine",
                url="http://ar-demo.tradesoft.pro/search.html?article=04C100032F",
            )

    def test_negative_quantity_raises_error(self):
        """Part quantities cannot be negative."""
        with pytest.raises(ValidationError):
            ParsedPart(
                part_no="04C100032F",
                description="base engine",
                url="http://ar-demo.tradesoft.pro/search.html?article=04C100032F",
                quantity=-1,
            )

    def test_zero_quantity_raises_error(self):
        """Part quantities must be at least 1."""
        with pytest.raises(ValidationError):
            ParsedPart(
                part_no="04C100032F",
                description="base engine",
                url="http://ar-demo.tradesoft.pro/search.html?article=04C100032F",
                quantity=0,
            )
