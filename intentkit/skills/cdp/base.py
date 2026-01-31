"""CDP wallet skills base class."""

from intentkit.skills.onchain import IntentKitOnChainSkill


class CDPBaseTool(IntentKitOnChainSkill):
    """Base class for CDP wallet skills.

    CDP skills provide basic wallet operations like getting balances,
    wallet details, and transferring native tokens.

    These skills work with any EVM-compatible wallet provider (CDP, Safe/Privy).
    """

    category: str = "cdp"
