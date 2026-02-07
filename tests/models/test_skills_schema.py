import pytest  # noqa: F401
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from intentkit.models.agent import Agent
from intentkit.models.llm import LLMModelInfoTable
from intentkit.models.skill import Skill, SkillTable


@pytest_asyncio.fixture()
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # Ensure tables for the models used in these tests exist
    async with engine.begin() as conn:
        await conn.run_sync(SkillTable.__table__.create)
        await conn.run_sync(LLMModelInfoTable.__table__.create)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()


async def _insert_erc20_skill(session, skill_name: str = "erc20_get_balance"):
    """Insert an ERC20 skill into the database.

    Args:
        session: Database session
        skill_name: The skill name to use (defaults to new naming convention)
    """
    from datetime import datetime, timezone
    from decimal import Decimal

    now = datetime.now(timezone.utc)
    session.add(
        SkillTable(
            name=skill_name,
            category="erc20",
            config_name=skill_name,  # config_name should match schema.json states
            enabled=True,
            price_level=3,
            price=Decimal("2"),
            price_self_key=Decimal("1.5"),
            rate_limit_count=None,
            rate_limit_minutes=None,
            author="tester",
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_get_all_preserves_config_name(session):
    """Test that Skill.get_all preserves the config_name from database."""
    await _insert_erc20_skill(session, "erc20_get_balance")

    skills = await Skill.get_all(session)
    skill_map = {skill.name: skill for skill in skills}

    erc20_skill = skill_map["erc20_get_balance"]
    assert erc20_skill.config_name == "erc20_get_balance"
    assert erc20_skill.category == "erc20"
    from decimal import Decimal

    assert erc20_skill.price == Decimal("2")


@pytest.mark.asyncio
async def test_get_all_with_none_config_name_merges_with_default(session):
    """Test that when config_name is None in DB, it gets merged with default skill's config_name.

    When a skill exists in both DB and defaults (CSV), the DB values override defaults,
    but None values are excluded from the merge (exclude_none=True), so the default
    config_name is preserved.
    """
    from datetime import datetime, timezone
    from decimal import Decimal

    now = datetime.now(timezone.utc)
    session.add(
        SkillTable(
            name="erc20_get_balance",
            category="erc20",
            config_name=None,  # Explicitly test None config_name
            enabled=True,
            price_level=3,
            price=Decimal("2"),
            price_self_key=Decimal("1.5"),
            rate_limit_count=None,
            rate_limit_minutes=None,
            author="tester",
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()

    skills = await Skill.get_all(session)
    skill_map = {skill.name: skill for skill in skills}

    erc20_skill = skill_map["erc20_get_balance"]
    # config_name from DB is None, but it gets merged with default skill's config_name
    # because exclude_none=True in model_dump() excludes None values from override
    assert erc20_skill.config_name == "erc20_get_balance"  # From default skill in CSV
    assert erc20_skill.category == "erc20"
    assert erc20_skill.price == Decimal("2")  # From DB override


@pytest.mark.asyncio
async def test_agent_get_json_schema_includes_category_when_db_has_skills(session):
    """Test that Agent.get_json_schema includes skill category when DB has enabled skills."""
    await _insert_erc20_skill(session, "erc20_get_balance")

    schema = await Agent.get_json_schema(session)

    skills_schema = schema["properties"]["skills"]["properties"]
    assert "erc20" in skills_schema
    states = skills_schema["erc20"]["properties"]["states"]["properties"]
    # Schema states come from schema.json, which uses new naming convention
    assert "erc20_get_balance" in states
    assert "erc20_transfer" in states
    assert "erc20_get_token_address" in states


@pytest.mark.asyncio
async def test_agent_get_json_schema_adds_price_level_from_db(session):
    """Test that Agent.get_json_schema adds x-price-level from DB to schema states."""
    await _insert_erc20_skill(session, "erc20_get_balance")

    schema = await Agent.get_json_schema(session)

    skills_schema = schema["properties"]["skills"]["properties"]
    assert "erc20" in skills_schema

    # Check that price level was added to the state
    states = skills_schema["erc20"]["properties"]["states"]["properties"]
    erc20_state = states.get("erc20_get_balance", {})
    # Price level should be added from DB
    assert erc20_state.get("x-price-level") == 3
