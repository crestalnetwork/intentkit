import pytest  # noqa: F401
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from intentkit.config.base import Base
from intentkit.models.agent import Agent
from intentkit.models.llm import LLMModelInfoTable


@pytest_asyncio.fixture()
async def session(db_engine):
    async with db_engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[LLMModelInfoTable.__table__],
        )

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session


@pytest.mark.asyncio
async def test_agent_get_json_schema_includes_skill_categories(session):
    """Test that Agent.get_json_schema includes skill categories from schema.json files."""
    schema = await Agent.get_json_schema(session)

    skills_schema = schema["properties"]["skills"]["properties"]
    # erc20 should be present since it has a schema.json
    assert "erc20" in skills_schema
    states = skills_schema["erc20"]["properties"]["states"]["properties"]
    assert "erc20_get_balance" in states
    assert "erc20_transfer" in states
