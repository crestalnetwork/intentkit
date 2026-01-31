"""ERC721 skills base class."""

from intentkit.skills.onchain import IntentKitOnChainSkill


class ERC721BaseTool(IntentKitOnChainSkill):
    """Base class for ERC721 NFT skills.

    ERC721 skills provide functionality to interact with NFT contracts
    including checking balances, minting, and transferring tokens.

    These skills work with any EVM-compatible wallet provider (CDP, Safe/Privy).
    """

    category: str = "erc721"
