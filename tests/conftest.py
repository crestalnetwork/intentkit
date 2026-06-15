import os
import sys
from pathlib import Path

# Tests must never send traces to LangSmith, even if the developer's shell or
# .env enables tracing. All four env var spellings the langsmith SDK accepts
# must be pinned before any intentkit import: the SDK caches env reads, so a
# value seen at import time would stick.
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGSMITH_TRACING_V2"] = "false"
os.environ["LANGCHAIN_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
# Likewise for Langfuse: it activates on key presence and registers a global
# LangChain callback at config import, so any agent/LLM run in the suite would
# emit traces. Blank the keys before intentkit.config loads so langfuse_tracing
# stays False. They must be SET to empty, not popped: config's load_dotenv()
# re-adds popped keys from .env, but won't override a key already present.
for _var in (
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
    "LANGFUSE_HOST",
):
    os.environ[_var] = ""
os.environ.setdefault("REDIS_HOST", "localhost")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine  # noqa: E402
from testing.postgresql import Postgresql  # noqa: E402

from intentkit.config import db as db_module  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def postgresql_server():
    server = Postgresql()
    try:
        yield server
    finally:
        server.stop()


@pytest_asyncio.fixture(scope="session")
async def postgres_engine(postgresql_server):
    db_url = postgresql_server.url()
    async_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(async_url)
    db_module.engine = engine
    try:
        yield engine
    finally:
        await engine.dispose()
        db_module.engine = None


async def _truncate_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        tables = [row[0] for row in result]
        if tables:
            table_names = ", ".join(f'"{table}"' for table in tables)
            await conn.execute(
                text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
            )


@pytest_asyncio.fixture()
async def db_engine(postgres_engine):
    await _truncate_tables(postgres_engine)
    try:
        yield postgres_engine
    finally:
        await _truncate_tables(postgres_engine)
