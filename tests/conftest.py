import os

# Override DATABASE_URL before any shared modules are imported so that
# shared/database.py does not attempt to connect to PostgreSQL (which is
# unavailable during unit-tests).  The value must be set prior to the first
# import of shared.config / shared.database.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from shared.models.base import Base
from shared.models import Brand, Market, Model, ModelYear, PartsCategory, Subgroup, Part

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# Tables that are compatible with SQLite (exclude PostgreSQL-only tables like crawl_queue)
SQLITE_COMPATIBLE_TABLES = [
    "brands",
    "markets",
    "models",
    "model_years",
    "parts_categories",
    "subgroups",
    "parts",
    "crawl_jobs",
]


def _create_sqlite_tables(conn):
    """Create only SQLite-compatible tables, skipping PostgreSQL-specific ones."""
    tables = [
        Base.metadata.tables[name]
        for name in SQLITE_COMPATIBLE_TABLES
        if name in Base.metadata.tables
    ]
    Base.metadata.create_all(conn, tables=tables)


def _drop_sqlite_tables(conn):
    """Drop only the SQLite-compatible tables that were created."""
    tables = [
        Base.metadata.tables[name]
        for name in reversed(SQLITE_COMPATIBLE_TABLES)
        if name in Base.metadata.tables
    ]
    Base.metadata.drop_all(conn, tables=tables)


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(_create_sqlite_tables)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(_drop_sqlite_tables)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def sample_brand(db_session):
    brand = Brand(
        name="Volkswagen",
        slug="volkswagen",
        region="Europe",
        catalog_path="/audivw/",
        catalog_url="https://catcar.info/audivw/",
    )
    db_session.add(brand)
    await db_session.flush()
    return brand


@pytest.fixture
async def sample_market(db_session, sample_brand):
    market = Market(
        brand_id=sample_brand.id,
        name="Europe",
        catalog_url="https://catcar.info/audivw/?l=europe",
    )
    db_session.add(market)
    await db_session.flush()
    return market


@pytest.fixture
async def sample_model(db_session, sample_brand, sample_market):
    model = Model(
        brand_id=sample_brand.id,
        market_id=sample_market.id,
        catalog_code="GOLF",
        name="Golf/Variant/4Motion",
        production_date="1998-...",
        catalog_url="https://catcar.info/audivw/?l=golf",
    )
    db_session.add(model)
    await db_session.flush()
    return model


@pytest.fixture
async def sample_model_year(db_session, sample_model):
    my = ModelYear(
        model_id=sample_model.id,
        year=2015,
        restriction="5G1",
        catalog_url="https://catcar.info/audivw/?l=golf2015",
    )
    db_session.add(my)
    await db_session.flush()
    return my


@pytest.fixture
async def sample_category(db_session, sample_model_year):
    cat = PartsCategory(
        model_year_id=sample_model_year.id,
        category_index=1,
        name="Engine",
        catalog_url="https://catcar.info/audivw/?l=engine",
    )
    db_session.add(cat)
    await db_session.flush()
    return cat


@pytest.fixture
async def sample_subgroup(db_session, sample_category):
    sg = Subgroup(
        category_id=sample_category.id,
        main_group="10",
        illustration_number="10003",
        description="Base engine",
        remark="1.0 ltr.",
        catalog_url="https://catcar.info/audivw/?l=baseengine",
    )
    db_session.add(sg)
    await db_session.flush()
    return sg


@pytest.fixture
async def sample_part(db_session, sample_subgroup):
    part = Part(
        subgroup_id=sample_subgroup.id,
        position="1",
        part_number="04C100032F",
        description="Short engine",
        quantity="1",
    )
    db_session.add(part)
    await db_session.flush()
    return part


@pytest.fixture
async def app_client(db_engine, db_session):
    """Create test client with overridden DB dependency."""
    from app.main import app
    from shared.database import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
