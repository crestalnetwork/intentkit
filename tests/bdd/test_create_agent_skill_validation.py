import pytest

from intentkit.core.agent.management import create_agent
from intentkit.models.agent import AgentCreate
from intentkit.utils.error import IntentKitAPIError

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.bdd
async def test_create_agent_rejects_invalid_skill_category():
    agent = AgentCreate(
        id="test-skill-val-1",
        name="Skill Test",
        model="gpt-4o-mini",
        skills={"nonexistent": {"enabled": True, "states": {"x": "public"}}},
    )
    with pytest.raises(IntentKitAPIError, match="nonexistent"):
        await create_agent(agent)


@pytest.mark.bdd
async def test_create_agent_rejects_invalid_skill_name():
    agent = AgentCreate(
        id="test-skill-val-2",
        name="Skill Test",
        model="gpt-4o-mini",
        skills={"ui": {"enabled": True, "states": {"fake_skill": "public"}}},
    )
    with pytest.raises(IntentKitAPIError, match="fake_skill"):
        await create_agent(agent)


@pytest.mark.bdd
async def test_create_agent_accepts_valid_skills():
    agent = AgentCreate(
        id="test-skill-val-3",
        name="Skill Test Valid",
        model="gpt-4o-mini",
        skills={"ui": {"enabled": True, "states": {"ui_show_card": "public"}}},
    )
    created, _ = await create_agent(agent)
    assert created.skills["ui"]["states"]["ui_show_card"] == "public"
