from intentkit.skills.onchain import IntentKitOnChainSkill


class AerodromeBaseTool(IntentKitOnChainSkill):
    """Base class for Aerodrome tools."""

    category: str = "aerodrome"
