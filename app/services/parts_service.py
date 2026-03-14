import math
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.part import Part
from shared.models.subgroup import Subgroup
from shared.models.parts_category import PartsCategory
from shared.models.model_year import ModelYear
from shared.models.model import Model
from shared.models.brand import Brand
from shared.utils import escape_like
from shared.config import settings


async def _build_breadcrumb(db: AsyncSession, subgroup_id: int) -> dict:
    """Build breadcrumb by joining up the hierarchy from subgroup."""
    result = await db.execute(
        select(Subgroup, PartsCategory, ModelYear, Model, Brand)
        .join(PartsCategory, Subgroup.category_id == PartsCategory.id)
        .join(ModelYear, PartsCategory.model_year_id == ModelYear.id)
        .join(Model, ModelYear.model_id == Model.id)
        .join(Brand, Model.brand_id == Brand.id)
        .where(Subgroup.id == subgroup_id)
    )
    row = result.first()
    if row is None:
        return {}

    subgroup, category, model_year, model, brand = row
    return {
        "brand": {"id": brand.id, "name": brand.name, "slug": brand.slug},
        "model": {"id": model.id, "name": model.name},
        "year": {"id": model_year.id, "year": model_year.year},
        "category": {"id": category.id, "name": category.name},
        "subgroup": {"id": subgroup.id, "description": subgroup.description},
    }


class PartsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _is_postgres() -> bool:
        return "postgresql" in settings.DATABASE_URL

    async def _search_parts(self, query, page=1, per_page=50):
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * per_page
        paged_query = query.offset(offset).limit(per_page)
        result = await self.db.execute(paged_query)
        parts = result.scalars().all()

        items = []
        for p in parts:
            breadcrumb = await _build_breadcrumb(self.db, p.subgroup_id)
            items.append({
                "id": p.id,
                "subgroup_id": p.subgroup_id,
                "position": p.position,
                "part_number": p.part_number,
                "description": p.description,
                "remark": p.remark,
                "quantity": p.quantity,
                "breadcrumb": breadcrumb,
            })

        pages = math.ceil(total / per_page) if total > 0 else 0
        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }

    async def search(self, query_str: str, page=1, per_page=50):
        escaped = escape_like(query_str)
        query = select(Part).where(
            Part.part_number.ilike(f"%{escaped}%") |
            Part.description.ilike(f"%{escaped}%")
        )
        return await self._search_parts(query, page, per_page)

    async def search_by_part_number(self, part_number: str, page=1, per_page=50):
        if self._is_postgres():
            query = select(Part).where(Part.part_number.op("%")(part_number))
        else:
            query = select(Part).where(Part.part_number.ilike(f"%{escape_like(part_number)}%"))
        return await self._search_parts(query, page, per_page)

    async def search_by_description(self, description: str, page=1, per_page=50):
        if self._is_postgres():
            from sqlalchemy import func as sa_func, column
            ts_query = sa_func.plainto_tsquery("english", description)
            query = select(Part).where(column("search_vector").op("@@")(ts_query))
        else:
            query = select(Part).where(Part.description.ilike(f"%{escape_like(description)}%"))
        return await self._search_parts(query, page, per_page)
