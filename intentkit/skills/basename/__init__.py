"""Basename AgentKit skills."""

from typing import TYPE_CHECKING, Optional, TypedDict

from coinbase_agentkit import basename_action_provider

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import (
    SkillConfig,
    SkillState,
    action_to_structured_tool,
    get_agentkit_actions,
)
from intentkit.skills.basename.base import BasenameBaseTool

if TYPE_CHECKING:
    from intentkit.models.agent import Agent


class SkillStates(TypedDict):
    BasenameActionProvider_register_basename: SkillState


class Config(SkillConfig):
    """Configuration for Basename skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    agent_id: str,
    agent: Optional["Agent"] = None,
    **_,
) -> list[BasenameBaseTool]:
    """Get all Basename skills."""

    available_skills: list[str] = []
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    actions = await get_agentkit_actions(
        agent_id, store, [basename_action_provider], agent=agent
    )
    tools: list[BasenameBaseTool] = []
    for skill in available_skills:
        for action in actions:
            if action.name.endswith(skill):
                tools.append(action_to_structured_tool(action))
    return tools
