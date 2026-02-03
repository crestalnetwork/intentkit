from intentkit.skills.onchain import IntentKitOnChainSkill


class LiFiBaseTool(IntentKitOnChainSkill):
    """Base class for LiFi tools."""

    category: str = "lifi"
