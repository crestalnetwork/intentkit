import logging
from typing import Any, TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.pancakeswap.add_liquidity import PancakeSwapAddLiquidity
from intentkit.skills.pancakeswap.base import PancakeSwapBaseTool
from intentkit.skills.pancakeswap.get_positions import PancakeSwapGetPositions
from intentkit.skills.pancakeswap.quote import PancakeSwapQuote
from intentkit.skills.pancakeswap.remove_liquidity import PancakeSwapRemoveLiquidity
from intentkit.skills.pancakeswap.swap import PancakeSwapSwap

logger = logging.getLogger(__name__)

_cache: dict[str, PancakeSwapBaseTool] = {}


class SkillStates(TypedDict):
    quote: SkillState
    swap: SkillState
    get_positions: SkillState
    add_liquidity: SkillState
    remove_liquidity: SkillState


class Config(SkillConfig):
    """Configuration for PancakeSwap skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    **_: Any,
) -> list[PancakeSwapBaseTool]:
    """Get all PancakeSwap skills."""
    available_skills: list[str] = []

    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    result: list[PancakeSwapBaseTool] = []
    for name in available_skills:
        skill = _get_skill(name)
        if skill:
            result.append(skill)
    return result


def _get_skill(name: str) -> PancakeSwapBaseTool | None:
    if name not in _cache:
        if name == "quote":
            _cache[name] = PancakeSwapQuote()
        elif name == "swap":
            _cache[name] = PancakeSwapSwap()
        elif name == "get_positions":
            _cache[name] = PancakeSwapGetPositions()
        elif name == "add_liquidity":
            _cache[name] = PancakeSwapAddLiquidity()
        elif name == "remove_liquidity":
            _cache[name] = PancakeSwapRemoveLiquidity()
        else:
            logger.warning("Unknown pancakeswap skill: %s", name)
            return None
    return _cache[name]


def available() -> bool:
    """PancakeSwap requires no platform API keys."""
    return True
