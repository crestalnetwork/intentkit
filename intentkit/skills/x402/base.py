from intentkit.skills.onchain import IntentKitOnChainSkill


class X402BaseSkill(IntentKitOnChainSkill):
    """Base class for x402 skills."""

    @property
    def category(self) -> str:
        return "x402"
