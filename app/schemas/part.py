from typing import Optional, Any, Dict
from pydantic import BaseModel


class BreadcrumbSchema(BaseModel):
    brand: Optional[Dict[str, Any]] = None
    model: Optional[Dict[str, Any]] = None
    year: Optional[Dict[str, Any]] = None
    category: Optional[Dict[str, Any]] = None
    subgroup: Optional[Dict[str, Any]] = None


class PartResponse(BaseModel):
    id: int
    subgroup_id: int
    position: Optional[str] = None
    part_number: str
    description: str
    remark: Optional[str] = None
    quantity: Optional[str] = None

    class Config:
        from_attributes = True


class PartSearchResponse(BaseModel):
    id: int
    subgroup_id: int
    position: Optional[str] = None
    part_number: str
    description: str
    remark: Optional[str] = None
    quantity: Optional[str] = None
    breadcrumb: BreadcrumbSchema

    class Config:
        from_attributes = True
