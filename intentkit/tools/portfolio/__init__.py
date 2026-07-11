"""Portfolio tools for blockchain wallet analysis."""

from intentkit.config.config import config as system_config
from intentkit.tools.meta import ToolsetMeta
from intentkit.tools.portfolio.base import PortfolioBaseTool
from intentkit.tools.portfolio.token_balances import TokenBalances
from intentkit.tools.portfolio.wallet_approvals import WalletApprovals
from intentkit.tools.portfolio.wallet_defi_positions import WalletDefiPositions
from intentkit.tools.portfolio.wallet_history import WalletHistory
from intentkit.tools.portfolio.wallet_net_worth import WalletNetWorth
from intentkit.tools.portfolio.wallet_nfts import WalletNFTs
from intentkit.tools.portfolio.wallet_profitability import WalletProfitability
from intentkit.tools.portfolio.wallet_profitability_summary import (
    WalletProfitabilitySummary,
)
from intentkit.tools.portfolio.wallet_stats import WalletStats
from intentkit.tools.portfolio.wallet_swaps import WalletSwaps

toolset = ToolsetMeta(
    title="Portfolio Analysis",
    description="Access blockchain wallet data and analytics through Moralis APIs for portfolio tracking, token balances, and investment performance",
    tags=["Analytics", "Crypto", "DeFi"],
    web3=True,
    icon="/tools/portfolio/moralis.png",
)


# Cache tools at the system level, because they are stateless
_cache: dict[str, PortfolioBaseTool] = {}

_TOOL_NAME_TO_CLASS_MAP: dict[str, type[PortfolioBaseTool]] = {
    "portfolio_wallet_history": WalletHistory,
    "portfolio_token_balances": TokenBalances,
    "portfolio_wallet_approvals": WalletApprovals,
    "portfolio_wallet_swaps": WalletSwaps,
    "portfolio_wallet_net_worth": WalletNetWorth,
    "portfolio_wallet_profitability_summary": WalletProfitabilitySummary,
    "portfolio_wallet_profitability": WalletProfitability,
    "portfolio_wallet_stats": WalletStats,
    "portfolio_wallet_defi_positions": WalletDefiPositions,
    "portfolio_wallet_nfts": WalletNFTs,
}


async def get_tools(tool_names: list[str], **_) -> list[PortfolioBaseTool]:
    """Return Portfolio tool instances for the requested names.

    Unknown names are skipped silently.
    """
    tools: list[PortfolioBaseTool] = []
    for name in tool_names:
        tool = get_portfolio_tool(name)
        if tool:
            tools.append(tool)
    return tools


def get_portfolio_tool(tool_name: str) -> PortfolioBaseTool | None:
    """Get a portfolio tool by name, with caching."""
    if tool_name in _cache:
        return _cache[tool_name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(tool_name)
    if not tool_class:
        return None

    _cache[tool_name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[tool_name]


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.moralis_api_key)
