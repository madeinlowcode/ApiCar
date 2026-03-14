from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.exceptions import AppException, register_exception_handlers
from app.api.v1.router import router as v1_router
from shared.database import AsyncSessionLocal
from shared.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        import redis.asyncio as aioredis
        app.state.redis_pool = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
    except Exception:
        app.state.redis_pool = None
    yield
    if getattr(app.state, "redis_pool", None):
        await app.state.redis_pool.aclose()


app = FastAPI(title="API CatCar", version="1.0.0", lifespan=lifespan)

# Register exception handlers
register_exception_handlers(app)

# Include v1 router
app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
async def health(request: Request):
    # Check database
    db_status = "disconnected"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception:
        pass

    # Check Redis (use shared pool, don't create a new connection per request)
    redis_status = "disconnected"
    try:
        pool = getattr(request.app.state, "redis_pool", None)
        if pool:
            await pool.ping()
            redis_status = "connected"
    except Exception:
        pass

    status = "healthy" if db_status == "connected" else "unhealthy"
    return {
        "status": status,
        "database": db_status,
        "redis": redis_status,
        "version": "1.0.0",
    }
