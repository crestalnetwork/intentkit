from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator
from urllib.parse import quote_plus

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from models.db_mig import safe_migrate

engine = None
_pool = None


async def init_db(
    host: str,
    username: str,
    password: str,
    dbname: str,
    port: Annotated[str, Field(default="5432", description="Database port")],
    auto_migrate: Annotated[
        bool, Field(default=True, description="Whether to run migrations automatically")
    ],
) -> None:
    """Initialize the database and handle schema updates.

    Args:
        host: Database host
        username: Database username
        password: Database password
        dbname: Database name
        port: Database port (default: 5432)
        auto_migrate: Whether to run migrations automatically (default: True)
    """
    global engine, _pool
    # Initialize psycopg pool if not already initialized
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=f"postgresql://{username}:{quote_plus(password)}@{host}:{port}/{dbname}",
            min_size=3,
            max_size=20,
            timeout=60,
            max_idle=30 * 60,
        )
    # Initialize SQLAlchemy engine with pool settings
    if engine is None:
        engine = create_async_engine(
            f"postgresql+asyncpg://{username}:{quote_plus(password)}@{host}:{port}/{dbname}",
            pool_size=20,  # Increase pool size
            max_overflow=30,  # Increase max overflow
            pool_timeout=60,  # Increase timeout
            pool_pre_ping=True,  # Enable connection health checks
            pool_recycle=3600,  # Recycle connections after 1 hour
        )
        if auto_migrate:
            await safe_migrate(engine)
            async with _pool.connection() as conn:
                await conn.set_autocommit(True)
                saver = AsyncPostgresSaver(conn)
                await saver.setup()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(engine) as session:
        yield session


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Get a database session using an async context manager.

    This function is designed to be used with the 'async with' statement,
    ensuring proper session cleanup.

    Returns:
        AsyncSession: A SQLAlchemy async session that will be automatically closed

    Example:
        ```python
        async with get_session() as session:
            # use session here
            session.query(...)
        # session is automatically closed
        ```
    """
    session = AsyncSession(engine)
    try:
        yield session
    finally:
        await session.close()


def get_engine() -> AsyncEngine:
    """Get the SQLAlchemy async engine.

    Returns:
        AsyncEngine: The SQLAlchemy async engine
    """
    return engine


def get_pool() -> AsyncConnectionPool:
    """Get the global psycopg connection pool.

    Returns:
        AsyncConnectionPool: The global psycopg connection pool
    """
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db first.")
    return _pool
