from intentkit.skills.onchain import IntentKitOnChainSkill


class PancakeSwapBaseTool(IntentKitOnChainSkill):
    """Base class for PancakeSwap tools."""

    category: str = "pancakeswap"
