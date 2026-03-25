import logging
from typing import Any, TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.uniswap.add_liquidity import UniswapAddLiquidity
from intentkit.skills.uniswap.base import UniswapBaseTool
from intentkit.skills.uniswap.get_positions import UniswapGetPositions
from intentkit.skills.uniswap.quote import UniswapQuote
from intentkit.skills.uniswap.remove_liquidity import UniswapRemoveLiquidity
from intentkit.skills.uniswap.swap import UniswapSwap

logger = logging.getLogger(__name__)

_cache: dict[str, UniswapBaseTool] = {}


class SkillStates(TypedDict):
    quote: SkillState
    swap: SkillState
    get_positions: SkillState
    add_liquidity: SkillState
    remove_liquidity: SkillState


class Config(SkillConfig):
    """Configuration for Uniswap skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    **_: Any,
) -> list[UniswapBaseTool]:
    """Get all Uniswap skills."""
    available_skills: list[str] = []

    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    result: list[UniswapBaseTool] = []
    for name in available_skills:
        skill = _get_skill(name)
        if skill:
            result.append(skill)
    return result


def _get_skill(name: str) -> UniswapBaseTool | None:
    if name not in _cache:
        if name == "quote":
            _cache[name] = UniswapQuote()
        elif name == "swap":
            _cache[name] = UniswapSwap()
        elif name == "get_positions":
            _cache[name] = UniswapGetPositions()
        elif name == "add_liquidity":
            _cache[name] = UniswapAddLiquidity()
        elif name == "remove_liquidity":
            _cache[name] = UniswapRemoveLiquidity()
        else:
            logger.warning("Unknown uniswap skill: %s", name)
            return None
    return _cache[name]


def available() -> bool:
    """Uniswap requires no platform API keys."""
    return True
