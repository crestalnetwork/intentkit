"""Dune skills for blockchain analytics via the Dune API."""

import logging
from collections.abc import Callable
from typing import TypedDict

from intentkit.config.config import config as system_config
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.dune.base import DuneBaseTool
from intentkit.skills.dune.execute_query import DuneExecuteQuery
from intentkit.skills.dune.get_query_results import DuneGetQueryResults
from intentkit.skills.dune.run_sql import DuneRunSQL

_cache: dict[str, DuneBaseTool] = {}

logger = logging.getLogger(__name__)

_SKILL_NAME_TO_CLASS: dict[str, Callable[[], DuneBaseTool]] = {
    "dune_execute_query": DuneExecuteQuery,
    "dune_get_query_results": DuneGetQueryResults,
    "dune_run_sql": DuneRunSQL,
}


class SkillStates(TypedDict):
    dune_execute_query: SkillState
    dune_get_query_results: SkillState
    dune_run_sql: SkillState


class Config(SkillConfig):
    """Configuration for Dune skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[DuneBaseTool]:
    """Get all enabled Dune skills."""
    available_skills = []

    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    result = []
    for name in available_skills:
        skill = _get_dune_skill(name)
        if skill:
            result.append(skill)
    return result


def _get_dune_skill(name: str) -> DuneBaseTool | None:
    """Get a Dune skill by name with caching."""
    if name in _cache:
        return _cache[name]

    cls = _SKILL_NAME_TO_CLASS.get(name)
    if cls is None:
        logger.warning("Unknown dune skill: %s", name)
        return None

    _cache[name] = cls()
    return _cache[name]


def available() -> bool:
    """Check if this skill category is available based on system config."""
    return bool(system_config.dune_api_key)
