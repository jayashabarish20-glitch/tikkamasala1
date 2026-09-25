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
    """Add stock columns to products table and delivery address columns to orders table."""
    async with engine.begin() as conn:
        def existing_columns(sync_conn, table_name):
            return {column["name"] for column in inspect(sync_conn).get_columns(table_name)}

        # Products table
        prod_columns = await conn.run_sync(lambda c: existing_columns(c, "products"))
        if "stock_quantity" not in prod_columns:
            await conn.execute(text("ALTER TABLE products ADD COLUMN stock_quantity INTEGER NOT NULL DEFAULT 0"))
        if "is_available" not in prod_columns:
            await conn.execute(text("ALTER TABLE products ADD COLUMN is_available BOOLEAN NOT NULL DEFAULT 1"))

        # Orders table - add delivery address fields
        order_columns = await conn.run_sync(lambda c: existing_columns(c, "orders"))
        if "delivery_house_flat_door" not in order_columns:
            await conn.execute(text("ALTER TABLE orders ADD COLUMN delivery_house_flat_door VARCHAR(100)"))
        if "delivery_street_area" not in order_columns:
            await conn.execute(text("ALTER TABLE orders ADD COLUMN delivery_street_area VARCHAR(200)"))
        if "delivery_city" not in order_columns:
            await conn.execute(text("ALTER TABLE orders ADD COLUMN delivery_city VARCHAR(100)"))
        if "delivery_state" not in order_columns:
            await conn.execute(text("ALTER TABLE orders ADD COLUMN delivery_state VARCHAR(100)"))
        if "delivery_pincode" not in order_columns:
            await conn.execute(text("ALTER TABLE orders ADD COLUMN delivery_pincode VARCHAR(10)"))
        if "delivery_landmark" not in order_columns:
            await conn.execute(text("ALTER TABLE orders ADD COLUMN delivery_landmark VARCHAR(200)"))
        if "payment_method" not in order_columns:
            await conn.execute(text("ALTER TABLE orders ADD COLUMN payment_method VARCHAR(20) DEFAULT 'ONLINE'"))
        if "payment_status" not in order_columns:
            await conn.execute(text("ALTER TABLE orders ADD COLUMN payment_status VARCHAR(20) DEFAULT 'PENDING'"))
