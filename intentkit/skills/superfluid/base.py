"""Superfluid skills base class."""

from intentkit.skills.onchain import IntentKitOnChainSkill


class SuperfluidBaseTool(IntentKitOnChainSkill):
    """Base class for Superfluid streaming payment skills.

    Superfluid skills provide functionality to create, update, and delete
    money streams using the Superfluid protocol. Streams allow continuous
    real-time payments.

    These skills work with any EVM-compatible wallet provider (CDP, Safe/Privy).
    """

    category: str = "superfluid"
