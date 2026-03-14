import math
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.model import Model
from shared.utils import escape_like
from shared.models.model_year import ModelYear
from shared.models.parts_category import PartsCategory
from shared.models.subgroup import Subgroup
from shared.models.part import Part


class ModelService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_model(self, model_id: int):
        result = await self.db.execute(select(Model).where(Model.id == model_id))
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return {
            "id": model.id,
            "brand_id": model.brand_id,
            "market_id": model.market_id,
            "catalog_code": model.catalog_code,
            "name": model.name,
            "production_date": model.production_date,
            "catalog_url": model.catalog_url,
        }

    async def get_model_years(self, model_id: int, year=None, page=1, per_page=50):
        # Verify model exists
        model_result = await self.db.execute(select(Model).where(Model.id == model_id))
        model = model_result.scalar_one_or_none()
        if model is None:
            return None

        query = select(ModelYear).where(ModelYear.model_id == model_id)
        if year:
            query = query.where(ModelYear.year == year)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        result = await self.db.execute(query)
        years = result.scalars().all()

        items = [
            {
                "id": y.id,
                "model_id": y.model_id,
                "year": y.year,
                "restriction": y.restriction,
                "catalog_url": y.catalog_url,
            }
            for y in years
        ]

        pages = math.ceil(total / per_page) if total > 0 else 0
        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }

    async def get_year_categories(self, year_id: int, page=1, per_page=50):
        # Verify year exists
        year_result = await self.db.execute(select(ModelYear).where(ModelYear.id == year_id))
        year = year_result.scalar_one_or_none()
        if year is None:
            return None

        query = select(PartsCategory).where(PartsCategory.model_year_id == year_id)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        result = await self.db.execute(query)
        categories = result.scalars().all()

        items = [
            {
                "id": c.id,
                "model_year_id": c.model_year_id,
                "category_index": c.category_index,
                "name": c.name,
                "catalog_url": c.catalog_url,
            }
            for c in categories
        ]

        pages = math.ceil(total / per_page) if total > 0 else 0
        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }

    async def get_category_subgroups(self, category_id: int, search=None, page=1, per_page=50):
        # Verify category exists
        cat_result = await self.db.execute(select(PartsCategory).where(PartsCategory.id == category_id))
        cat = cat_result.scalar_one_or_none()
        if cat is None:
            return None

        query = select(Subgroup).where(Subgroup.category_id == category_id)
        if search:
            query = query.where(Subgroup.description.ilike(f"%{escape_like(search)}%"))

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        result = await self.db.execute(query)
        subgroups = result.scalars().all()

        items = [
            {
                "id": s.id,
                "category_id": s.category_id,
                "main_group": s.main_group,
                "illustration_number": s.illustration_number,
                "description": s.description,
                "remark": s.remark,
                "catalog_url": s.catalog_url,
            }
            for s in subgroups
        ]

        pages = math.ceil(total / per_page) if total > 0 else 0
        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }

    async def get_subgroup_parts(self, subgroup_id: int, page=1, per_page=50):
        # Verify subgroup exists
        sg_result = await self.db.execute(select(Subgroup).where(Subgroup.id == subgroup_id))
        sg = sg_result.scalar_one_or_none()
        if sg is None:
            return None

        query = select(Part).where(Part.subgroup_id == subgroup_id)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        result = await self.db.execute(query)
        parts = result.scalars().all()

        items = [
            {
                "id": p.id,
                "subgroup_id": p.subgroup_id,
                "position": p.position,
                "part_number": p.part_number,
                "description": p.description,
                "remark": p.remark,
                "quantity": p.quantity,
            }
            for p in parts
        ]

        pages = math.ceil(total / per_page) if total > 0 else 0
        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }
