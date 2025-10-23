"""Portfolio skills for blockchain wallet analysis."""

import logging
from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.portfolio.base import PortfolioBaseTool
from intentkit.skills.portfolio.token_balances import TokenBalances
from intentkit.skills.portfolio.wallet_approvals import WalletApprovals
from intentkit.skills.portfolio.wallet_defi_positions import WalletDefiPositions
from intentkit.skills.portfolio.wallet_history import WalletHistory
from intentkit.skills.portfolio.wallet_net_worth import WalletNetWorth
from intentkit.skills.portfolio.wallet_nfts import WalletNFTs
from intentkit.skills.portfolio.wallet_profitability import WalletProfitability
from intentkit.skills.portfolio.wallet_profitability_summary import (
    WalletProfitabilitySummary,
)
from intentkit.skills.portfolio.wallet_stats import WalletStats
from intentkit.skills.portfolio.wallet_swaps import WalletSwaps

# Cache skills at the system level, because they are stateless
_cache: dict[str, PortfolioBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    """State configurations for Portfolio skills."""

    wallet_history: SkillState
    token_balances: SkillState
    wallet_approvals: SkillState
    wallet_swaps: SkillState
    wallet_net_worth: SkillState
    wallet_profitability_summary: SkillState
    wallet_profitability: SkillState
    wallet_stats: SkillState
    wallet_defi_positions: SkillState
    wallet_nfts: SkillState


class Config(SkillConfig):
    """Configuration for Portfolio blockchain analysis skills."""

    states: SkillStates
    api_key: str
    api_key_provider: str


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[PortfolioBaseTool]:
    """Get all Portfolio blockchain analysis skills.

    Args:
        config: The configuration for Portfolio skills.
        is_private: Whether to include private skills.

    Returns:
        A list of Portfolio blockchain analysis skills.
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
        skill = get_portfolio_skill(name)
        if skill:
            result.append(skill)
    return result


def get_portfolio_skill(
    name: str,
) -> PortfolioBaseTool:
    """Get a portfolio skill by name."""
    if name == "wallet_history":
        if name not in _cache:
            _cache[name] = WalletHistory()
        return _cache[name]
    elif name == "token_balances":
        if name not in _cache:
            _cache[name] = TokenBalances()
        return _cache[name]
    elif name == "wallet_approvals":
        if name not in _cache:
            _cache[name] = WalletApprovals()
        return _cache[name]
    elif name == "wallet_swaps":
        if name not in _cache:
            _cache[name] = WalletSwaps()
        return _cache[name]
    elif name == "wallet_net_worth":
        if name not in _cache:
            _cache[name] = WalletNetWorth()
        return _cache[name]
    elif name == "wallet_profitability_summary":
        if name not in _cache:
            _cache[name] = WalletProfitabilitySummary()
        return _cache[name]
    elif name == "wallet_profitability":
        if name not in _cache:
            _cache[name] = WalletProfitability()
        return _cache[name]
    elif name == "wallet_stats":
        if name not in _cache:
            _cache[name] = WalletStats()
        return _cache[name]
    elif name == "wallet_defi_positions":
        if name not in _cache:
            _cache[name] = WalletDefiPositions()
        return _cache[name]
    elif name == "wallet_nfts":
        if name not in _cache:
            _cache[name] = WalletNFTs()
        return _cache[name]
    else:
        raise ValueError(f"Unknown portfolio skill: {name}")
