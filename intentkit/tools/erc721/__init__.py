"""ERC721 NFT tools."""

from intentkit.tools.erc721.base import ERC721BaseTool
from intentkit.tools.erc721.get_balance import ERC721GetBalance
from intentkit.tools.erc721.mint import ERC721Mint
from intentkit.tools.erc721.transfer import ERC721Transfer
from intentkit.tools.meta import ToolsetMeta

toolset = ToolsetMeta(
    title="ERC721",
    description="ERC721 NFT management actions including balance checking, minting, and transfers",
    tags=["Crypto", "NFT"],
    web3=True,
    icon="/tools/erc721/erc721.svg",
)


# Cache for tool instances
_cache: dict[str, ERC721BaseTool] = {
    "erc721_get_balance": ERC721GetBalance(),
    "erc721_mint": ERC721Mint(),
    "erc721_transfer": ERC721Transfer(),
}


async def get_tools(tool_names: list[str], **_) -> list[ERC721BaseTool]:
    """Get the requested ERC721 tools."""
    return [_cache[name] for name in tool_names if name in _cache]


def available() -> bool:
    """Check if this toolset is available based on system config.

    ERC721 tools are available for any EVM-compatible wallet (CDP, Safe/Privy).
    They don't require specific CDP credentials since they work with any wallet.
    """
    return True
