from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import quote_plus

from langgraph.checkpoint.postgres.shallow import AsyncShallowPostgresSaver
from psycopg import OperationalError
from psycopg_pool import AsyncConnectionPool
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from intentkit.models.db_mig import safe_migrate

engine: AsyncEngine | None = None
_connection_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncShallowPostgresSaver | None = None


async def check_connection(conn):
    """
    Pre-ping function to validate connection health before returning to application.
    This helps handle database restarts and failovers gracefully.
    """
    try:
        await conn.execute("SELECT 1")
    except OperationalError:
        # Re-raise the exception to let the connection pool know this connection is broken
        raise


async def init_db(
    host: str | None,
    username: str | None,
    password: str | None,
    dbname: str | None,
    port: Annotated[str | None, Field(default="5432", description="Database port")],
    auto_migrate: Annotated[
        bool, Field(default=True, description="Whether to run migrations automatically")
    ],
    pool_size: Annotated[
        int, Field(default=3, description="Database connection pool size")
    ] = 3,
) -> None:
    """Initialize the database and handle schema updates.

    Args:
        host: Database host
        username: Database username
        password: Database password
        dbname: Database name
        port: Database port (default: 5432)
        auto_migrate: Whether to run migrations automatically (default: True)
        pool_size: Database connection pool size (default: 3)
    """
    global engine, _connection_pool, _checkpointer
    # Initialize psycopg pool and AsyncShallowPostgresSaver if not already initialized
    if _connection_pool is None:
        if host:
            conn_string = (
                f"postgresql://{username}:{quote_plus(password)}@{host}:{port}/{dbname}"
            )
            pool = AsyncConnectionPool(
                conninfo=conn_string,
                min_size=pool_size,
                max_size=pool_size * 2,
                timeout=60,
                max_idle=30 * 60,
                # Add health check function to handle database restarts
                check=check_connection,
                # Set connection max lifetime to prevent stale connections
                max_lifetime=3600,  # 1 hour
            )
            _connection_pool = pool
            _checkpointer = AsyncShallowPostgresSaver(pool)
            if auto_migrate:
                # Migrate can not use pool, so we start from scratch
                async with AsyncShallowPostgresSaver.from_conn_string(
                    conn_string
                ) as saver:
                    await saver.setup()
        else:
            # For in-memory, we don't need a pool, but we need to handle it if requested
            pass
    # Initialize SQLAlchemy engine with pool settings
    if engine is None:
        if host:
            engine = create_async_engine(
                f"postgresql+asyncpg://{username}:{quote_plus(password)}@{host}:{port}/{dbname}",
                pool_size=pool_size,
                max_overflow=pool_size * 2,  # Set overflow to 2x pool size
                pool_timeout=60,  # Increase timeout
                pool_pre_ping=True,  # Enable connection health checks
                pool_recycle=3600,  # Recycle connections after 1 hour
            )
        else:
            engine = create_async_engine(
                "sqlite+aiosqlite:///:memory:",
                connect_args={"check_same_thread": False},
            )
        if auto_migrate:
            await safe_migrate(engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    assert engine is not None, "Database engine not initialized. Call init_db first."
    async with AsyncSession(engine) as session:
        yield session


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
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
    assert engine is not None, "Database engine not initialized. Call init_db first."
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
    assert engine is not None, "Database engine not initialized. Call init_db first."
    return engine


def get_connection_pool() -> AsyncConnectionPool:
    """Get the AsyncConnectionPool instance.

    Returns:
        AsyncConnectionPool: The AsyncConnectionPool instance
    """
    if _connection_pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db first.")
    return _connection_pool


def get_checkpointer() -> AsyncShallowPostgresSaver:
    """Get the AsyncShallowPostgresSaver instance.

    Returns:
        AsyncShallowPostgresSaver: The AsyncShallowPostgresSaver instance
    """
    if _checkpointer is None:
        raise RuntimeError("Database checkpointer not initialized. Call init_db first.")
    return _checkpointer
