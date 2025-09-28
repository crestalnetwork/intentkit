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


async def _insert_wow_skill(session):
    from datetime import datetime, timezone
    from decimal import Decimal

    now = datetime.now(timezone.utc)
    session.add(
        SkillTable(
            name="WowActionProvider_buy_token",
            category="wow",
            config_name=None,
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
async def test_get_all_preserves_default_config_name(session):
    await _insert_wow_skill(session)

    skills = await Skill.get_all(session)
    skill_map = {skill.name: skill for skill in skills}

    wow_buy = skill_map["WowActionProvider_buy_token"]
    assert wow_buy.config_name == "WowActionProvider_buy_token"
    assert wow_buy.category == "wow"
    from decimal import Decimal

    assert wow_buy.price == Decimal("2")


@pytest.mark.asyncio
async def test_agent_get_json_schema_includes_category_when_db_overrides(session):
    await _insert_wow_skill(session)

    schema = await Agent.get_json_schema(session)

    skills_schema = schema["properties"]["skills"]["properties"]
    assert "wow" in skills_schema
    states = skills_schema["wow"]["properties"]["states"]["properties"]
    assert "WowActionProvider_buy_token" in states
