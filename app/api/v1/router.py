from fastapi import APIRouter

from app.api.v1 import brands, models, years, categories, subgroups, search, admin

router = APIRouter()

router.include_router(brands.router)
router.include_router(models.router)
router.include_router(years.router)
router.include_router(categories.router)
router.include_router(subgroups.router)
router.include_router(search.router)
router.include_router(admin.router)
