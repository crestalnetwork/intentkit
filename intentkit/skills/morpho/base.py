"""Morpho skills base class."""

from intentkit.skills.onchain import IntentKitOnChainSkill


class MorphoBaseTool(IntentKitOnChainSkill):
    """Base class for Morpho lending protocol skills.

    Morpho skills provide functionality to interact with Morpho Vaults
    including depositing and withdrawing assets.

    These skills work with any EVM-compatible wallet provider (CDP, Safe/Privy).
    """

    category: str = "morpho"
