from intentkit.skills.onchain import IntentKitOnChainSkill


class UniswapBaseTool(IntentKitOnChainSkill):
    """Base class for Uniswap tools."""

    category: str = "uniswap"
