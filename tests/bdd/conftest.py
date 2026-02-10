import os

import pytest
import pytest_asyncio
from dotenv import load_dotenv

# Load .env file for BDD tests
load_dotenv()

# Override DB_NAME to use 'bdd' database
os.environ["DB_NAME"] = "bdd"


def pytest_collection_modifyitems(items) -> None:
    """Mark all tests in this directory as BDD tests automatically."""
    for item in items:
        item.add_marker(pytest.mark.bdd)


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def setup_bdd_database():
    """Drop and recreate 'bdd' database before BDD tests run, and initialize tables."""
    import psycopg

    from intentkit.config.db import init_db
    from intentkit.config.redis import init_redis

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    username = os.getenv("DB_USERNAME", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    bdd_db = "bdd"

    # Connect to 'postgres' database to drop/create the bdd database
    conn_string = f"host={host} port={port} dbname=postgres"
    if username:
        conn_string += f" user={username}"
    if password:
        conn_string += f" password={password}"

    # Use synchronous psycopg for setup (drop/create database)
    with psycopg.connect(conn_string, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Terminate existing connections to bdd database
            _ = cur.execute(
                """
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = %s AND pid <> pg_backend_pid()
            """,
                (bdd_db,),
            )
            # Drop and recreate
            _ = cur.execute(f"DROP DATABASE IF EXISTS {bdd_db}")
            _ = cur.execute(f"CREATE DATABASE {bdd_db}")

    # Initialize tables using init_db (which runs migrations if auto_migrate=True)
    # This runs in the same event loop as the tests
    await init_db(
        host=host,
        username=username,
        password=password,
        dbname=bdd_db,
        port=port,
        auto_migrate=True,
    )

    # Initialize Redis (needed for LLMModelInfo caching, etc.)
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_db = int(os.getenv("REDIS_DB", "0"))
    redis_password = os.getenv("REDIS_PASSWORD")
    redis_ssl = os.getenv("REDIS_SSL", "false") == "true"
    await init_redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        password=redis_password,
        ssl=redis_ssl,
    )

    yield

    # Cleanup after tests: close the engine to release connections
    from intentkit.config import db
    from intentkit.config.redis import get_redis

    if db.engine:
        await db.engine.dispose()
    if db._connection_pool:
        await db._connection_pool.close()
    try:
        redis_client = get_redis()
        await redis_client.aclose()
    except RuntimeError:
        pass
