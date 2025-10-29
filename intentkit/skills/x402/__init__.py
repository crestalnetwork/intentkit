"""x402 skill category."""

import logging
from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.x402.ask_agent import X402AskAgent
from intentkit.skills.x402.base import X402BaseSkill

logger = logging.getLogger(__name__)

_cache: dict[str, X402BaseSkill] = {}


class SkillStates(TypedDict):
    x402_ask_agent: SkillState


class Config(SkillConfig):
    """Configuration for x402 skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[X402BaseSkill]:
    """Return enabled x402 skills for the agent."""
    enabled_skills = []
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            enabled_skills.append(skill_name)

    result: list[X402BaseSkill] = []
    for name in enabled_skills:
        skill = _get_skill(name)
        if skill:
            result.append(skill)
    return result


def _get_skill(name: str) -> X402BaseSkill | None:
    if name == "x402_ask_agent":
        if name not in _cache:
            _cache[name] = X402AskAgent()
        return _cache[name]

    logger.warning("Unknown x402 skill requested: %s", name)
    return None
