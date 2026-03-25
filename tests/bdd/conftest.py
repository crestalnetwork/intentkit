import os

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy.engine.url import make_url

# Load .env file for BDD tests
load_dotenv()

os.environ["DB_NAME"] = "bdd"


def pytest_collection_modifyitems(items) -> None:
    """Mark all tests in this directory as BDD tests automatically."""
    for item in items:
        item.add_marker(pytest.mark.bdd)


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def setup_bdd_database(postgresql_server):
    import psycopg

    from intentkit.config.db import init_db
    from intentkit.config.redis import init_redis

    url = make_url(postgresql_server.url())
    host = url.host or "localhost"
    port = str(url.port or 5432)
    username = url.username or "postgres"
    password = url.password or ""
    bdd_db = "bdd"
    os.environ["DB_HOST"] = host
    os.environ["DB_PORT"] = port
    os.environ["DB_USERNAME"] = username
    os.environ["DB_PASSWORD"] = password
    os.environ["DB_NAME"] = bdd_db

    conn_string = f"host={host} port={port} dbname=postgres"
    if username:
        conn_string += f" user={username}"
    if password:
        conn_string += f" password={password}"

    with psycopg.connect(conn_string, autocommit=True) as conn:
        with conn.cursor() as cur:
            _ = cur.execute(
                """
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = %s AND pid <> pg_backend_pid()
            """,
                (bdd_db,),
            )
            _ = cur.execute(f"DROP DATABASE IF EXISTS {bdd_db}")
            _ = cur.execute(f"CREATE DATABASE {bdd_db}")

    await init_db(
        host=host,
        username=username,
        password=password,
        dbname=bdd_db,
        port=port,
        auto_migrate=True,
    )

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
    if db.connection_pool:
        await db.connection_pool.close()
    try:
        redis_client = get_redis()
        await redis_client.aclose()
    except RuntimeError:
        pass
