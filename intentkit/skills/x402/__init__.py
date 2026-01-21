"""x402 skill category."""

import logging
from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.x402.base import X402BaseSkill
from intentkit.skills.x402.check_price import X402CheckPrice
from intentkit.skills.x402.get_orders import X402GetOrders
from intentkit.skills.x402.http_request import X402HttpRequest
from intentkit.skills.x402.pay import X402Pay

logger = logging.getLogger(__name__)

_cache: dict[str, X402BaseSkill] = {}


class SkillStates(TypedDict):
    x402_http_request: SkillState
    x402_check_price: SkillState
    x402_pay: SkillState
    x402_get_orders: SkillState


class Config(SkillConfig):
    """Configuration for x402 skills."""

    states: SkillStates


_SKILL_BUILDERS: dict[str, type[X402BaseSkill]] = {
    "x402_http_request": X402HttpRequest,
    "x402_check_price": X402CheckPrice,
    "x402_pay": X402Pay,
    "x402_get_orders": X402GetOrders,
}


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
    builder = _SKILL_BUILDERS.get(name)
    if builder:
        if name not in _cache:
            _cache[name] = builder()
        return _cache[name]
    logger.warning("Unknown x402 skill requested: %s", name)
    return None


def available() -> bool:
    """Check if this skill category is available based on system config."""
    return True
