import os

import pytest
from dotenv import load_dotenv

# Load .env file for BDD tests
load_dotenv()

# Override DB_NAME to use 'bdd' database
os.environ["DB_NAME"] = "bdd"


def pytest_collection_modifyitems(items):
    """Mark all tests in this directory as BDD tests automatically."""
    for item in items:
        item.add_marker(pytest.mark.bdd)


@pytest.fixture(scope="session", autouse=True)
def setup_bdd_database():
    """Drop and recreate 'bdd' database before BDD tests run."""
    import psycopg

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

    # Use synchronous psycopg for setup
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

    yield

    # Cleanup after tests (optional: drop database)
    # Uncomment the following if you want to drop the database after tests:
    # with psycopg.connect(conn_string, autocommit=True) as conn:
    #     with conn.cursor() as cur:
    #         cur.execute(f"DROP DATABASE IF EXISTS {bdd_db}")
