from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator, Optional
from urllib.parse import quote_plus

from intentkit.models.db_mig import safe_migrate
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Checkpointer
from psycopg_pool import AsyncConnectionPool
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

engine = None
_langgraph_checkpointer: Optional[Checkpointer] = None


async def init_db(
    host: Optional[str],
    username: Optional[str],
    password: Optional[str],
    dbname: Optional[str],
    port: Annotated[Optional[str], Field(default="5432", description="Database port")],
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
    global engine, _langgraph_checkpointer
    # Initialize psycopg pool and AsyncPostgresSaver if not already initialized
    if _langgraph_checkpointer is None:
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
            )
            _langgraph_checkpointer = AsyncPostgresSaver(pool)
            if auto_migrate:
                # Migrate can not use pool, so we start from scratch
                async with AsyncPostgresSaver.from_conn_string(conn_string) as saver:
                    await saver.setup()
        else:
            _langgraph_checkpointer = InMemorySaver()
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


def get_langgraph_checkpointer() -> Checkpointer:
    """Get the AsyncPostgresSaver instance for langgraph.

    Returns:
        AsyncPostgresSaver: The AsyncPostgresSaver instance
    """
    if _langgraph_checkpointer is None:
        raise RuntimeError("Database pool not initialized. Call init_db first.")
    return _langgraph_checkpointer
