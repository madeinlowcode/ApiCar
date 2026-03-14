from typing import List, Optional
from pydantic import BaseModel


class MarketSchema(BaseModel):
    id: int
    name: str
    catalog_url: str

    class Config:
        from_attributes = True


class BrandResponse(BaseModel):
    id: int
    name: str
    slug: str
    region: str
    logo_url: Optional[str] = None

    class Config:
        from_attributes = True


class BrandDetailResponse(BaseModel):
    id: int
    name: str
    slug: str
    region: str
    logo_url: Optional[str] = None
    markets: List[MarketSchema] = []

    class Config:
        from_attributes = True
