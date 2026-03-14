import math
from typing import Generic, List, TypeVar, Any

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    per_page: int
    pages: int

    class Config:
        arbitrary_types_allowed = True


def paginate(items: list, total: int, page: int, per_page: int) -> dict:
    pages = math.ceil(total / per_page) if total > 0 else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }
