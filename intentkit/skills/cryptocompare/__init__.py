"""CryptoCompare skills."""

import logging
from typing import TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.cryptocompare.base import CryptoCompareBaseTool
from intentkit.skills.cryptocompare.fetch_news import CryptoCompareFetchNews
from intentkit.skills.cryptocompare.fetch_price import CryptoCompareFetchPrice
from intentkit.skills.cryptocompare.fetch_top_exchanges import (
    CryptoCompareFetchTopExchanges,
)
from intentkit.skills.cryptocompare.fetch_top_market_cap import (
    CryptoCompareFetchTopMarketCap,
)
from intentkit.skills.cryptocompare.fetch_top_volume import CryptoCompareFetchTopVolume
from intentkit.skills.cryptocompare.fetch_trading_signals import (
    CryptoCompareFetchTradingSignals,
)

# Cache skills at the system level, because they are stateless
_cache: dict[str, CryptoCompareBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    fetch_news: SkillState
    fetch_price: SkillState
    fetch_trading_signals: SkillState
    fetch_top_market_cap: SkillState
    fetch_top_exchanges: SkillState
    fetch_top_volume: SkillState


class Config(SkillConfig):
    """Configuration for CryptoCompare skills."""

    states: SkillStates
    api_key: str


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[CryptoCompareBaseTool]:
    """Get all CryptoCompare skills.

    Args:
        config: The configuration for CryptoCompare skills.
        is_private: Whether to include private skills.
        store: The skill store for persisting data.

    Returns:
        A list of CryptoCompare skills.
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
        skill = get_cryptocompare_skill(name, store)
        if skill:
            result.append(skill)
    return result


def get_cryptocompare_skill(
    name: str,
    store: SkillStoreABC,
) -> CryptoCompareBaseTool:
    """Get a CryptoCompare skill by name.

    Args:
        name: The name of the skill to get
        store: The skill store for persisting data

    Returns:
        The requested CryptoCompare skill
    """

    if name == "fetch_news":
        if name not in _cache:
            _cache[name] = CryptoCompareFetchNews(
                skill_store=store,
            )
        return _cache[name]
    elif name == "fetch_price":
        if name not in _cache:
            _cache[name] = CryptoCompareFetchPrice(
                skill_store=store,
            )
        return _cache[name]
    elif name == "fetch_trading_signals":
        if name not in _cache:
            _cache[name] = CryptoCompareFetchTradingSignals(
                skill_store=store,
            )
        return _cache[name]
    elif name == "fetch_top_market_cap":
        if name not in _cache:
            _cache[name] = CryptoCompareFetchTopMarketCap(
                skill_store=store,
            )
        return _cache[name]
    elif name == "fetch_top_exchanges":
        if name not in _cache:
            _cache[name] = CryptoCompareFetchTopExchanges(
                skill_store=store,
            )
        return _cache[name]
    elif name == "fetch_top_volume":
        if name not in _cache:
            _cache[name] = CryptoCompareFetchTopVolume(
                skill_store=store,
            )
        return _cache[name]
    else:
        logger.warning(f"Unknown CryptoCompare skill: {name}")
        return None
