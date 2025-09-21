"""ERC20 AgentKit skills."""

from typing import TypedDict

from coinbase_agentkit import erc20_action_provider

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import (
    SkillConfig,
    SkillState,
    action_to_structured_tool,
    get_agentkit_actions,
)
from intentkit.skills.erc20.base import ERC20BaseTool


class SkillStates(TypedDict):
    ERC20ActionProvider_get_balance: SkillState
    ERC20ActionProvider_transfer: SkillState


class Config(SkillConfig):
    """Configuration for ERC20 skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    agent_id: str,
    **_,
) -> list[ERC20BaseTool]:
    """Get all ERC20 skills."""

    available_skills: list[str] = []
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    actions = await get_agentkit_actions(agent_id, store, [erc20_action_provider])
    tools: list[ERC20BaseTool] = []
    for skill in available_skills:
        for action in actions:
            if action.name.endswith(skill):
                tools.append(action_to_structured_tool(action))
    return tools
