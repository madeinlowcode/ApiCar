from typing import Optional
from pydantic import BaseModel, field_validator


class ParsedModel(BaseModel):
    code: str
    name: str
    url: str
    production_date: str
    description: Optional[str] = None
    markets: Optional[str] = None
    market: str = "Europe"

    @field_validator("code")
    @classmethod
    def code_must_not_be_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("code must not be empty")
        return v

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("name must not be empty")
        return v

    @field_validator("url")
    @classmethod
    def url_must_not_be_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("url must not be empty")
        return v

    @field_validator("production_date")
    @classmethod
    def production_date_must_not_be_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("production_date must not be empty")
        return v


class ParsedModelYear(BaseModel):
    year: int
    url: str
    restriction: Optional[str] = None

    @field_validator("year", mode="before")
    @classmethod
    def year_must_be_valid(cls, v):
        try:
            year_int = int(v)
        except (ValueError, TypeError):
            raise ValueError("year must be a numeric value")
        if year_int < 1900 or year_int > 2100:
            raise ValueError("year must be between 1900 and 2100")
        return year_int

    @field_validator("url")
    @classmethod
    def url_must_not_be_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("url must not be empty")
        return v


class ParsedCategory(BaseModel):
    name: str
    url: str

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("name must not be empty")
        return v

    @field_validator("url")
    @classmethod
    def url_must_not_be_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("url must not be empty")
        return v


class ParsedSubgroup(BaseModel):
    ill_no: str
    description: str
    url: str
    remark: Optional[str] = None
    model_data: Optional[str] = None

    @field_validator("ill_no")
    @classmethod
    def ill_no_must_not_be_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("ill_no must not be empty")
        return v

    @field_validator("description")
    @classmethod
    def description_must_not_be_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("description must not be empty")
        return v

    @field_validator("url")
    @classmethod
    def url_must_not_be_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("url must not be empty")
        return v
