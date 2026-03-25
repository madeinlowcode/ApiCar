from typing import Optional
from pydantic import BaseModel, field_validator


class ParsedPart(BaseModel):
    part_no: str
    description: str
    url: str
    position: Optional[str] = None
    remark: Optional[str] = None
    quantity: Optional[str] = None
    model_data: Optional[str] = None

    @field_validator("part_no")
    @classmethod
    def part_no_must_not_be_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("part_no must not be empty")
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

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v):
        if v is not None and v.isdigit() and int(v) <= 0:
            raise ValueError("quantity must be at least 1")
        return v
