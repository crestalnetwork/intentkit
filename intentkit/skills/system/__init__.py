"""System skills."""

import logging
from typing import TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillOwnerState
from intentkit.skills.system.add_autonomous_task import AddAutonomousTask
from intentkit.skills.system.base import SystemBaseTool
from intentkit.skills.system.delete_autonomous_task import DeleteAutonomousTask
from intentkit.skills.system.edit_autonomous_task import EditAutonomousTask
from intentkit.skills.system.list_autonomous_tasks import ListAutonomousTasks
from intentkit.skills.system.read_agent_api_key import ReadAgentApiKey
from intentkit.skills.system.regenerate_agent_api_key import RegenerateAgentApiKey

# Cache skills at the system level, because they are stateless
_cache: dict[str, SystemBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    read_agent_api_key: SkillOwnerState
    regenerate_agent_api_key: SkillOwnerState
    list_autonomous_tasks: SkillOwnerState
    add_autonomous_task: SkillOwnerState
    delete_autonomous_task: SkillOwnerState
    edit_autonomous_task: SkillOwnerState


class Config(SkillConfig):
    """Configuration for system skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[SystemBaseTool]:
    """Get all system skills.

    Args:
        config: The configuration for system skills.
        is_private: Whether to include private skills.
        store: The skill store for persisting data.

    Returns:
        A list of system skills.
    """
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    result = []
    for name in available_skills:
        skill = get_system_skill(name, store)
        if skill:
            result.append(skill)
    return result


def get_system_skill(
    name: str,
    store: SkillStoreABC,
) -> SystemBaseTool:
    """Get a system skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested system skill
    """
    if name == "read_agent_api_key":
        if name not in _cache:
            _cache[name] = ReadAgentApiKey(
                skill_store=store,
            )
        return _cache[name]
    elif name == "regenerate_agent_api_key":
        if name not in _cache:
            _cache[name] = RegenerateAgentApiKey(
                skill_store=store,
            )
        return _cache[name]
    elif name == "list_autonomous_tasks":
        if name not in _cache:
            _cache[name] = ListAutonomousTasks(
                skill_store=store,
            )
        return _cache[name]
    elif name == "add_autonomous_task":
        if name not in _cache:
            _cache[name] = AddAutonomousTask(
                skill_store=store,
            )
        return _cache[name]
    elif name == "delete_autonomous_task":
        if name not in _cache:
            _cache[name] = DeleteAutonomousTask(
                skill_store=store,
            )
        return _cache[name]
    elif name == "edit_autonomous_task":
        if name not in _cache:
            _cache[name] = EditAutonomousTask(
                skill_store=store,
            )
        return _cache[name]
    else:
        logger.warning(f"Unknown system skill: {name}")
        return None
