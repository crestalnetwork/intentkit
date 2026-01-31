"""WETH skills base class."""

from intentkit.skills.onchain import IntentKitOnChainSkill


class WethBaseTool(IntentKitOnChainSkill):
    """Base class for WETH wrapping/unwrapping skills.

    WETH skills provide functionality to wrap ETH to WETH and unwrap WETH to ETH.
    WETH (Wrapped ETH) is an ERC20 token representation of ETH.

    These skills work with any EVM-compatible wallet provider (CDP, Safe/Privy).
    """

    category: str = "weth"
