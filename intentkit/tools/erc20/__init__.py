"""ERC20 token tools."""

from intentkit.tools.erc20.base import ERC20BaseTool
from intentkit.tools.erc20.get_balance import ERC20GetBalance
from intentkit.tools.erc20.get_token_address import ERC20GetTokenAddress
from intentkit.tools.erc20.transfer import ERC20Transfer
from intentkit.tools.meta import ToolsetMeta

toolset = ToolsetMeta(
    title="ERC20",
    description="ERC20 token balance, transfer, and lookup actions",
    tags=["Crypto", "DeFi"],
    web3=True,
    icon="/tools/erc20/erc20.svg",
)


# Cache for tool instances
_cache: dict[str, ERC20BaseTool] = {
    "erc20_get_balance": ERC20GetBalance(),
    "erc20_transfer": ERC20Transfer(),
    "erc20_get_token_address": ERC20GetTokenAddress(),
}


async def get_tools(tool_names: list[str], **_) -> list[ERC20BaseTool]:
    """Get the requested ERC20 tools."""
    return [_cache[name] for name in tool_names if name in _cache]


def available() -> bool:
    """Check if this toolset is available based on system config.

    ERC20 tools are available for any EVM-compatible wallet (CDP, Safe/Privy).
    They don't require specific CDP credentials since they work with any wallet.
    """
    return True
