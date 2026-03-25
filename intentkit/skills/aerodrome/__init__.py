import logging
from typing import Any, TypedDict

from intentkit.skills.aerodrome.add_liquidity import AerodromeAddLiquidity
from intentkit.skills.aerodrome.base import AerodromeBaseTool
from intentkit.skills.aerodrome.get_positions import AerodromeGetPositions
from intentkit.skills.aerodrome.quote import AerodromeQuote
from intentkit.skills.aerodrome.remove_liquidity import AerodromeRemoveLiquidity
from intentkit.skills.aerodrome.swap import AerodromeSwap
from intentkit.skills.base import SkillConfig, SkillState

logger = logging.getLogger(__name__)

_cache: dict[str, AerodromeBaseTool] = {}


class SkillStates(TypedDict):
    quote: SkillState
    swap: SkillState
    get_positions: SkillState
    add_liquidity: SkillState
    remove_liquidity: SkillState


class Config(SkillConfig):
    """Configuration for Aerodrome skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    **_: Any,
) -> list[AerodromeBaseTool]:
    """Get all Aerodrome skills."""
    available_skills: list[str] = []

    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    result: list[AerodromeBaseTool] = []
    for name in available_skills:
        skill = _get_skill(name)
        if skill:
            result.append(skill)
    return result


def _get_skill(name: str) -> AerodromeBaseTool | None:
    if name not in _cache:
        if name == "quote":
            _cache[name] = AerodromeQuote()
        elif name == "swap":
            _cache[name] = AerodromeSwap()
        elif name == "get_positions":
            _cache[name] = AerodromeGetPositions()
        elif name == "add_liquidity":
            _cache[name] = AerodromeAddLiquidity()
        elif name == "remove_liquidity":
            _cache[name] = AerodromeRemoveLiquidity()
        else:
            logger.warning("Unknown aerodrome skill: %s", name)
            return None
    return _cache[name]


def available() -> bool:
    """Aerodrome requires no platform API keys."""
    return True
