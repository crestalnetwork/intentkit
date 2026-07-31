import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import quote_plus

import psycopg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from intentkit.config.migration import run_migrations
from intentkit.utils.readiness import wait_until_ready

logger = logging.getLogger(__name__)

engine: AsyncEngine | None = None
connection_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None


async def _migrate_shallow_to_full(saver: AsyncPostgresSaver) -> None:
    """Drop shallow-format checkpoint tables so AsyncPostgresSaver.setup() can recreate them.

    AsyncShallowPostgresSaver used a different schema (no checkpoint_id column,
    different primary keys). The two migration histories are incompatible, so the
    cleanest path is to drop all checkpoint tables and let setup() rebuild from
    scratch. Checkpoint data is ephemeral conversation state, safe to discard.
    """
    async with saver._cursor() as cur:  # pyright: ignore[reportPrivateUsage]
        # Check if the old shallow schema is present
        row = await (
            await cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'checkpoints'"
            )
        ).fetchone()
        if row is None:
            return  # No checkpoint tables at all — fresh DB

        col = await (
            await cur.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'checkpoints' AND column_name = 'checkpoint_id'"
            )
        ).fetchone()
        if col is not None:
            return  # Already has checkpoint_id — full schema, nothing to do

        logger.info("Migrating checkpoint tables from shallow to full format …")
        await cur.execute("DROP TABLE IF EXISTS checkpoint_writes CASCADE")
        await cur.execute("DROP TABLE IF EXISTS checkpoint_blobs CASCADE")
        await cur.execute("DROP TABLE IF EXISTS checkpoints CASCADE")
        await cur.execute("DROP TABLE IF EXISTS checkpoint_migrations CASCADE")


async def check_connection(conn):
    """
    Pre-ping function to validate connection health before returning to application.
    This helps handle database restarts and failovers gracefully.
    """
    # An OperationalError here propagates to the connection pool, which is how
    # it learns the connection is broken.
    await conn.execute("SELECT 1")


# NOTE: Two separate connection pools are intentionally used here.
# langgraph-checkpoint-postgres requires psycopg (psycopg3) via AsyncConnectionPool,
# while SQLAlchemy uses asyncpg as its async driver. These are different PostgreSQL
# client libraries with incompatible connection pool implementations, so they cannot
# be consolidated into a single pool. This is a known architectural constraint.


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
    global engine, connection_pool, _checkpointer
    if not host:
        # The in-memory sqlite fallback (no host) has no pool or migration
        # story — it exists only so the package imports without a database.
        if engine is None:
            engine = create_async_engine(
                "sqlite+aiosqlite:///:memory:",
                connect_args={"check_same_thread": False},
            )
        return

    # Handle local PostgreSQL without authentication
    username_str = username or ""
    password_str = quote_plus(password) if password else ""
    auth = f"{username_str}:{password_str}@" if (username_str or password_str) else ""
    dsn = f"{auth}{host}:{port}/{dbname}"
    conn_string = f"postgresql://{dsn}"

    # Services restart in arbitrary order, so Postgres may still be booting
    # when we get here; wait for it to accept connections instead of failing
    # the start (and alerting) on the first touch below. A dedicated probe
    # rather than AsyncConnectionPool's own connect retry because migrations
    # must run first, on their own connections.
    async def _probe() -> None:
        async with await psycopg.AsyncConnection.connect(
            conn_string, connect_timeout=5
        ):
            pass

    await wait_until_ready("PostgreSQL", _probe, (psycopg.OperationalError,))

    # Upgrade the schema to head before anything touches the database. Runs on
    # every start; a Postgres advisory lock inside alembic/env.py serializes
    # concurrent starters, and an already-current schema is a fast no-op.
    if auto_migrate:
        await asyncio.to_thread(run_migrations, f"postgresql+psycopg://{dsn}")
    # Initialize psycopg pool and AsyncPostgresSaver if not already initialized
    if connection_pool is None:
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
            open=False,
        )
        await pool.open()
        connection_pool = pool  # pyright: ignore[reportAssignmentType]
        _checkpointer = AsyncPostgresSaver(pool)  # pyright: ignore[reportArgumentType]
        if auto_migrate:
            # Migrate can not use pool, so we start from scratch
            async with AsyncPostgresSaver.from_conn_string(conn_string) as saver:
                await _migrate_shallow_to_full(saver)
                await saver.setup()
    # Initialize SQLAlchemy engine with pool settings
    if engine is None:
        engine = create_async_engine(
            f"postgresql+asyncpg://{dsn}",
            pool_size=pool_size,
            max_overflow=pool_size * 2,  # Set overflow to 2x pool size
            pool_timeout=60,  # Increase timeout
            pool_pre_ping=True,  # Enable connection health checks
            pool_recycle=3600,  # Recycle connections after 1 hour
        )


async def get_db() -> AsyncGenerator[AsyncSession]:
    assert engine is not None, "Database engine not initialized. Call init_db first."
    async with AsyncSession(engine) as session:
        yield session


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession]:
    """Get a database session using an async context manager.

    This function is designed to be used with the 'async with' statement,
    ensuring proper session cleanup.

    Returns:
        AsyncSession: A SQLAlchemy async session that will be automatically closed

    Example:
        ```python
        async with get_session() as session:
            result = await session.execute(select(MyModel).where(...))
            items = result.scalars().all()
        # session is automatically closed
        ```
    """
    assert engine is not None, "Database engine not initialized. Call init_db first."
    session = AsyncSession(engine)
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
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
    if connection_pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db first.")
    return connection_pool


def get_checkpointer() -> AsyncPostgresSaver:
    """Get the AsyncPostgresSaver instance.

    Returns:
        AsyncPostgresSaver: The AsyncPostgresSaver instance
    """
    if _checkpointer is None:
        raise RuntimeError("Database checkpointer not initialized. Call init_db first.")
    return _checkpointer
