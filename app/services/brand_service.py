import math
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.models.brand import Brand
from shared.models.market import Market
from shared.models.model import Model
from shared.utils import escape_like


class BrandService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_brands(self, region=None, search=None, page=1, per_page=50):
        query = select(Brand)

        if region:
            query = query.where(Brand.region == region)
        if search:
            query = query.where(Brand.name.ilike(f"%{escape_like(search)}%"))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        result = await self.db.execute(query)
        brands = result.scalars().all()

        items = [
            {
                "id": b.id,
                "name": b.name,
                "slug": b.slug,
                "region": b.region,
                "logo_url": b.logo_url,
            }
            for b in brands
        ]

        pages = math.ceil(total / per_page) if total > 0 else 0
        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }

    async def get_brand_by_slug(self, slug: str):
        query = select(Brand).options(selectinload(Brand.markets)).where(Brand.slug == slug)
        result = await self.db.execute(query)
        brand = result.scalar_one_or_none()

        if brand is None:
            return None

        markets = [
            {"id": m.id, "name": m.name, "catalog_url": m.catalog_url}
            for m in brand.markets
        ]

        return {
            "id": brand.id,
            "name": brand.name,
            "slug": brand.slug,
            "region": brand.region,
            "logo_url": brand.logo_url,
            "markets": markets,
        }

    async def get_brand_models(self, slug: str, market_id=None, search=None, page=1, per_page=50):
        # First get the brand
        brand_query = select(Brand).where(Brand.slug == slug)
        brand_result = await self.db.execute(brand_query)
        brand = brand_result.scalar_one_or_none()

        if brand is None:
            return None

        query = select(Model).where(Model.brand_id == brand.id)

        if market_id:
            query = query.where(Model.market_id == market_id)
        if search:
            query = query.where(Model.name.ilike(f"%{escape_like(search)}%"))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        result = await self.db.execute(query)
        models = result.scalars().all()

        items = [
            {
                "id": m.id,
                "brand_id": m.brand_id,
                "market_id": m.market_id,
                "catalog_code": m.catalog_code,
                "name": m.name,
                "production_date": m.production_date,
                "catalog_url": m.catalog_url,
            }
            for m in models
        ]

        pages = math.ceil(total / per_page) if total > 0 else 0
        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }
