"""ERC20 skills base class."""

from intentkit.skills.onchain import IntentKitOnChainSkill


class ERC20BaseTool(IntentKitOnChainSkill):
    """Base class for ERC20 token skills.

    ERC20 skills provide functionality to interact with ERC20 tokens
    including checking balances, transferring tokens, and managing approvals.

    These skills work with any EVM-compatible wallet provider (CDP, Safe/Privy).
    """

    category: str = "erc20"
