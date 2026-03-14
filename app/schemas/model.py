from typing import Optional
from pydantic import BaseModel


class ModelResponse(BaseModel):
    id: int
    brand_id: int
    market_id: int
    catalog_code: str
    name: str
    production_date: Optional[str] = None
    catalog_url: str

    class Config:
        from_attributes = True


class ModelDetailResponse(ModelResponse):
    pass


class ModelYearResponse(BaseModel):
    id: int
    model_id: int
    year: int
    restriction: Optional[str] = None
    catalog_url: str

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    id: int
    model_year_id: int
    category_index: int
    name: str
    catalog_url: str

    class Config:
        from_attributes = True


class SubgroupResponse(BaseModel):
    id: int
    category_id: int
    main_group: str
    illustration_number: str
    description: str
    remark: Optional[str] = None
    catalog_url: str

    class Config:
        from_attributes = True
