"""Polymarket prediction market skills."""

import logging
from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.polymarket.base import PolymarketBaseTool
from intentkit.skills.polymarket.cancel_order import CancelOrder
from intentkit.skills.polymarket.get_market import GetMarket
from intentkit.skills.polymarket.get_orderbook import GetOrderbook
from intentkit.skills.polymarket.get_orders import GetOrders
from intentkit.skills.polymarket.get_positions import GetPositions
from intentkit.skills.polymarket.get_price_history import GetPriceHistory
from intentkit.skills.polymarket.get_trades import GetTrades
from intentkit.skills.polymarket.place_order import PlaceOrder
from intentkit.skills.polymarket.search_markets import SearchMarkets

# Cache skills at the system level, because they are stateless
_cache: dict[str, PolymarketBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    search_markets: SkillState
    get_market: SkillState
    get_orderbook: SkillState
    get_price_history: SkillState
    place_order: SkillState
    cancel_order: SkillState
    get_positions: SkillState
    get_orders: SkillState
    get_trades: SkillState


_SKILL_NAME_TO_CLASS_MAP: dict[str, type[PolymarketBaseTool]] = {
    "search_markets": SearchMarkets,
    "get_market": GetMarket,
    "get_orderbook": GetOrderbook,
    "get_price_history": GetPriceHistory,
    "place_order": PlaceOrder,
    "cancel_order": CancelOrder,
    "get_positions": GetPositions,
    "get_orders": GetOrders,
    "get_trades": GetTrades,
}


class Config(SkillConfig):
    """Configuration for Polymarket skills."""

    enabled: bool
    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[PolymarketBaseTool]:
    """Get all Polymarket skills based on config.

    Args:
        config: The configuration for Polymarket skills.
        is_private: Whether to include private skills.

    Returns:
        A list of Polymarket skills.
    """
    available_skills = []

    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    logger.debug("Available Polymarket skills: %s", available_skills)

    result = []
    for name in available_skills:
        skill = _get_skill(name)
        if skill:
            result.append(skill)
    return result


def _get_skill(name: str) -> PolymarketBaseTool | None:
    """Get a Polymarket skill by name, with caching."""
    if name in _cache:
        return _cache[name]

    skill_class = _SKILL_NAME_TO_CLASS_MAP.get(name)
    if not skill_class:
        logger.warning("Unknown Polymarket skill: %s", name)
        return None

    _cache[name] = skill_class()
    return _cache[name]


def available() -> bool:
    """Check if Polymarket skills are available.

    Always returns True since public skills need no API keys.
    Authenticated skills check wallet at runtime.
    """
    return True
