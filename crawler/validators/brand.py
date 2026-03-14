from pydantic import BaseModel, field_validator


class ParsedBrand(BaseModel):
    name: str
    url: str

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("name must not be empty or whitespace")
        return v

    @field_validator("url")
    @classmethod
    def url_must_not_be_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("url must not be empty or whitespace")
        return v
