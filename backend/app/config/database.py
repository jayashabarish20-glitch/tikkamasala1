"""
Database engine and session configuration.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import inspect, text
from app.config.settings import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

_engine_kwargs = dict(echo=False)
if _is_sqlite:
    from sqlalchemy.pool import StaticPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = StaticPool
else:
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_recycle"] = 3600

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def migrate_schema():
    """Add stock columns to an existing products table without dropping data."""
    async with engine.begin() as conn:
        def existing_columns(sync_conn):
            return {column["name"] for column in inspect(sync_conn).get_columns("products")}

        columns = await conn.run_sync(existing_columns)
        if "stock_quantity" not in columns:
            await conn.execute(text("ALTER TABLE products ADD COLUMN stock_quantity INTEGER NOT NULL DEFAULT 0"))
        if "is_available" not in columns:
            await conn.execute(text("ALTER TABLE products ADD COLUMN is_available BOOLEAN NOT NULL DEFAULT 1"))
