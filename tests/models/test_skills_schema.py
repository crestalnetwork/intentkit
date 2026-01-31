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


async def _insert_wow_skill(session, skill_name: str = "wow_buy_token"):
    """Insert a WOW skill into the database.

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
            category="wow",
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
    await _insert_wow_skill(session, "wow_buy_token")

    skills = await Skill.get_all(session)
    skill_map = {skill.name: skill for skill in skills}

    wow_buy = skill_map["wow_buy_token"]
    assert wow_buy.config_name == "wow_buy_token"
    assert wow_buy.category == "wow"
    from decimal import Decimal

    assert wow_buy.price == Decimal("2")


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
            name="wow_buy_token",
            category="wow",
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

    wow_buy = skill_map["wow_buy_token"]
    # config_name from DB is None, but it gets merged with default skill's config_name
    # because exclude_none=True in model_dump() excludes None values from override
    assert wow_buy.config_name == "wow_buy_token"  # From default skill in CSV
    assert wow_buy.category == "wow"
    assert wow_buy.price == Decimal("2")  # From DB override


@pytest.mark.asyncio
async def test_agent_get_json_schema_includes_category_when_db_has_skills(session):
    """Test that Agent.get_json_schema includes skill category when DB has enabled skills."""
    await _insert_wow_skill(session, "wow_buy_token")

    schema = await Agent.get_json_schema(session)

    skills_schema = schema["properties"]["skills"]["properties"]
    assert "wow" in skills_schema
    states = skills_schema["wow"]["properties"]["states"]["properties"]
    # Schema states come from schema.json, which uses new naming convention
    assert "wow_buy_token" in states
    assert "wow_create_token" in states
    assert "wow_sell_token" in states


@pytest.mark.asyncio
async def test_agent_get_json_schema_adds_price_level_from_db(session):
    """Test that Agent.get_json_schema adds x-price-level from DB to schema states."""
    await _insert_wow_skill(session, "wow_buy_token")

    schema = await Agent.get_json_schema(session)

    skills_schema = schema["properties"]["skills"]["properties"]
    assert "wow" in skills_schema

    # Check that price level was added to the state
    states = skills_schema["wow"]["properties"]["states"]["properties"]
    wow_buy_state = states.get("wow_buy_token", {})
    # Price level should be added from DB
    assert wow_buy_state.get("x-price-level") == 3
