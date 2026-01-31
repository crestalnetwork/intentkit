"""WOW skills base class."""

from intentkit.skills.onchain import IntentKitOnChainSkill


class WowBaseTool(IntentKitOnChainSkill):
    """Base class for WOW tools."""

    category: str = "wow"
