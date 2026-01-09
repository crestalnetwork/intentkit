"""Superfluid AgentKit skills."""

from typing import TypedDict

from coinbase_agentkit import superfluid_action_provider

from intentkit.config.config import config as system_config
from intentkit.models.agent import Agent
from intentkit.skills.base import (
    SkillConfig,
    SkillState,
    action_to_structured_tool,
    get_agentkit_actions,
)
from intentkit.skills.superfluid.base import SuperfluidBaseTool


class SkillStates(TypedDict):
    SuperfluidActionProvider_create_flow: SkillState
    SuperfluidActionProvider_delete_flow: SkillState
    SuperfluidActionProvider_update_flow: SkillState


class Config(SkillConfig):
    """Configuration for Superfluid skills."""

    states: SkillStates


async def get_skills(
    config: Config,
    is_private: bool,
    agent_id: str,
    agent: Agent | None = None,
    **_,
) -> list[SuperfluidBaseTool]:
    """Get all Superfluid skills."""

    available_skills: list[str] = []
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    actions = await get_agentkit_actions(
        agent_id, [superfluid_action_provider], agent=agent
    )
    tools: list[SuperfluidBaseTool] = []
    for skill in available_skills:
        for action in actions:
            if action.name.endswith(skill):
                tools.append(action_to_structured_tool(action))
    return tools


def available() -> bool:
    """Check if this skill category is available based on system config."""
    return all(
        [
            bool(system_config.cdp_api_key_id),
            bool(system_config.cdp_api_key_secret),
            bool(system_config.cdp_wallet_secret),
        ]
    )
