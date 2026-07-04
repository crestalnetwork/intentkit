"""Wallet Portfolio Tools for IntentKit."""

from collections.abc import Callable

from intentkit.config.config import config as system_config
from intentkit.tools.moralis.base import WalletBaseTool
from intentkit.tools.moralis.fetch_chain_portfolio import FetchChainPortfolio
from intentkit.tools.moralis.fetch_nft_portfolio import FetchNftPortfolio
from intentkit.tools.moralis.fetch_solana_portfolio import FetchSolanaPortfolio
from intentkit.tools.moralis.fetch_wallet_portfolio import FetchWalletPortfolio

_TOOL_CLASSES: dict[str, Callable[[], WalletBaseTool]] = {
    "moralis_fetch_wallet_portfolio": FetchWalletPortfolio,
    "moralis_fetch_chain_portfolio": FetchChainPortfolio,
    "moralis_fetch_nft_portfolio": FetchNftPortfolio,
    "moralis_fetch_solana_portfolio": FetchSolanaPortfolio,
}


async def get_tools(tool_names: list[str], **_) -> list[WalletBaseTool]:
    """Get the requested Wallet Portfolio tools; unknown names are skipped."""
    return [tool for name in tool_names if (tool := get_wallet_tool(name))]


def get_wallet_tool(tool_name: str) -> WalletBaseTool | None:
    """Get a specific Wallet Portfolio tool by name."""
    cls = _TOOL_CLASSES.get(tool_name)
    if cls is None:
        return None
    return cls()


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.moralis_api_key)
